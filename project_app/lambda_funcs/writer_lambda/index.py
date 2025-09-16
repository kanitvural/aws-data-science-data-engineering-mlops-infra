import os
import json
import sys
import boto3
import logging
import base64
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

region = os.environ["REGION"]
table_name = os.environ["TABLE_NAME"]  
dynamodb = boto3.resource('dynamodb', region_name=region)

def lambda_handler(event, context):
    raw_table = dynamodb.Table(table_name) 
    
    for record in event["Records"]:
        
        payload = base64.b64decode(record["kinesis"]["data"]).decode("utf-8")
        data = json.loads(payload)
        
        record_id = data["id"]        
        dep_delay = data.get("dep_delay")
        
        # Float -> Decimal for DynamoDB
        if dep_delay is not None:
            dep_delay = Decimal(str(dep_delay))
        
        raw_table.update_item(
            Key={"id": record_id},
            UpdateExpression="SET dep_delay = :d",
            ExpressionAttributeValues={":d": dep_delay}
        )
        logger.info(f"Updated Raw table: id {record_id} -> dep_delay={dep_delay}")
        
    return {"status": "success"}