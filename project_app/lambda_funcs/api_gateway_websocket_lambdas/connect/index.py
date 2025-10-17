import os
import boto3
import time
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

region = os.environ["REGION"]
table_name = os.environ["TABLE_NAME"]

def lambda_handler(event, context):
    connection_id = event["requestContext"]["connectionId"]

    # Save to DynamoDB
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    table.put_item(
        Item={
            "connectionId": connection_id,
            "timestamp": int(time.time()),
        }
    )

    logger.info(f"✅ User connected and saved: {connection_id}")
    return {"statusCode": 200}
