import os
import boto3
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

    # Delete from DynamoDB
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    table.delete_item(Key={"connectionId": connection_id})

    logger.info(f"❌ User disconnected and removed: {connection_id}")
    return {"statusCode": 200}
