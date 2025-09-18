import os
import json
import sys
import boto3
import logging
import base64
from decimal import Decimal

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# -----------------------------
# Environment variables
# -----------------------------
region = os.environ["REGION"]
table_name = os.environ["TABLE_NAME"]

# -----------------------------
# DynamoDB client
# -----------------------------
dynamodb = boto3.resource("dynamodb", region_name=region)
table = dynamodb.Table(table_name)

# -----------------------------
# Lambda handler
# -----------------------------
def lambda_handler(event, context):
    for record in event["Records"]:
        try:
            # Kinesis payload decode
            payload = base64.b64decode(record["kinesis"]["data"]).decode("utf-8")
            data = json.loads(payload)

            record_id = data["id"]
            timestamp = int(data["timestamp"])  # DynamoDB NUMBER sort key
            dep_delay = data.get("dep_delay")

            if dep_delay is not None:
                dep_delay = Decimal(str(dep_delay))  # DynamoDB float->Decimal

            # Update dep_delay for the correct item
            table.update_item(
                Key={
                    "id": record_id,
                    "timestamp": timestamp
                },
                UpdateExpression="SET dep_delay = :d",
                ExpressionAttributeValues={":d": dep_delay},
                ReturnValues="UPDATED_NEW"
            )

            logger.info(f"Updated Raw table: id={record_id}, timestamp={timestamp}, dep_delay={dep_delay}")
        except Exception as e:
            logger.error(f"Error processing record: {e}, payload={record}")
    
    return {"status": "success"}
