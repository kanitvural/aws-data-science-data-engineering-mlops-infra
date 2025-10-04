

# DynamoDB tablosunda şöyle bir GSI olacak:

# Index Name: flights-timestamp-index

# Partition Key: pk → sabit değer "flights"

# Sort Key: timestamp → UTC formatında timestamp

# Bu GSI, real-time query için kullanılacak, PK id’yi bozmayacağız.


import boto3
import pandas as pd
import logging
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key

# DynamoDB resource
dynamodb = boto3.resource("dynamodb", region_name="eu-central-1")
table = dynamodb.Table("raw-flights")

# Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

def query_recent_flights(minutes: int = 5) -> pd.DataFrame:
    """
    Query last 'minutes' of flights using GSI (fast, cost-efficient).
    Assumes a GSI 'flights-timestamp-index' with pk='flights' and sort key='timestamp'.
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=minutes)

    try:
        response = table.query(
            IndexName="flights-timestamp-index",
            KeyConditionExpression=Key("pk").eq("flights") & 
                                   Key("timestamp").between(start_time.isoformat(), end_time.isoformat())
        )
        items = response.get("Items", [])

        # Pagination
        while "LastEvaluatedKey" in response:
            response = table.query(
                IndexName="flights-timestamp-index",
                KeyConditionExpression=Key("pk").eq("flights") & 
                                       Key("timestamp").between(start_time.isoformat(), end_time.isoformat()),
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))

        df = pd.DataFrame(items)
        logger.info(f"✅ Found {len(df)} flights in the last {minutes} minutes")
        return df

    except Exception as e:
        logger.error(f"❌ Error querying recent flights: {str(e)}")
        raise

# Örnek kullanım
df = query_recent_flights(5)
print("Number of recent flights:", len(df))
