import os
import json
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from typing import List, Dict, Any

table_name = os.environ("TABLE_NAME")
region = os.environ.get("REGION")
limit = int(os.environ.get("LIMIT", 50))  

dynamodb = boto3.resource("dynamodb", region_name=region)
table = dynamodb.Table(table_name)


def decimal_to_float(obj: Any) -> Any:
    if isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


def fetch_flights(limit: int = limit) -> List[Dict[str, Any]]:

    try:
        
        response = table.scan(Limit=limit*3) 
        items = response.get("Items", [])
        items.sort(key=lambda x: float(x.get("timestamp", 0)), reverse=True)

        # limit kadar al
        return items[:limit]

    except Exception as e:
        print(f"[ERROR] Fetching flights: {e}")
        raise


def lambda_handler(event, context):
    try:
        flights = fetch_flights(limit)
        flights = decimal_to_float(flights) 

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(flights),
        }

    except Exception as e:
        print(f"[ERROR] Lambda handler: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
