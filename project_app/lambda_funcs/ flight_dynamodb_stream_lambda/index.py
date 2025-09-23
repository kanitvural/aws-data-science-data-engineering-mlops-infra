import os
import json
import boto3
import logging
import sys


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

api_endpoint = os.environ["API_GATEWAY_WEBSOCKET_ENDPOINT"]  
region = os.environ["REGION"]
table_name = os.environ["TABLE_NAME"]

def lambda_handler(event, context):
    # WebSocket API endpoint
    apigateway = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=api_endpoint,
    )

    for record in event["Records"]:
        event_name = record["eventName"]
        logger.info(f"Event: {event_name}")

        if event_name == "INSERT":
            # New flight data inserted
            new_image = record["dynamodb"]["NewImage"]
            flight_data = deserialize_dynamodb_json(new_image)

            message = {"type": "NEW_FLIGHT", "data": flight_data}

            # Log message for testing
            logger.info(f"Message sent: {json.dumps(message, default=str)}")

            # Send to WebSocket
            send_to_all_connections(apigateway, message)

        elif event_name == "MODIFY":
            # Data updated (dep_delay predicted)
            old_image = record["dynamodb"].get("OldImage", {})
            new_image = record["dynamodb"]["NewImage"]

            # Check if dep_delay changed
            old_dep_delay = old_image.get("dep_delay", {}).get("NULL", True)
            new_dep_delay = new_image.get("dep_delay", {}).get("N")

            if old_dep_delay and new_dep_delay:
                flight_data = deserialize_dynamodb_json(new_image)

                message = {"type": "DELAY_PREDICTED", "data": flight_data}

                logger.info(f"Delay prediction: {json.dumps(message, default=str)}")
                send_to_all_connections(apigateway, message)

    return {"statusCode": 200}


def deserialize_dynamodb_json(item):
    """Convert DynamoDB JSON to normal JSON"""
    def deserialize_value(value):
        if isinstance(value, dict):
            if "S" in value:  # String
                return value["S"]
            elif "N" in value:  # Number
                return float(value["N"])
            elif "NULL" in value:  # Null
                return None
            elif "M" in value:  # Map
                return {k: deserialize_value(v) for k, v in value["M"].items()}
            elif "L" in value:  # List
                return [deserialize_value(v) for v in value["L"]]
        return value

    return {key: deserialize_value(value) for key, value in item.items()}


def send_to_all_connections(apigateway, message):
    # Fetch connections from DynamoDB instead of using fixed ID
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    response = table.scan()
    connections = response["Items"]

    logger.info(f"📡 Sending to {len(connections)} active users")

    for connection in connections:
        connection_id = connection["connectionId"]
        try:
            apigateway.post_to_connection(
                ConnectionId=connection_id, Data=json.dumps(message, default=str)
            )
            logger.info(f"✅ Sent: {connection_id}")
        except Exception as e:
            table.delete_item(Key={"connectionId": connection_id})
            logger.warning(f"🗑️ Disconnected client removed: {connection_id} ({str(e)})")
