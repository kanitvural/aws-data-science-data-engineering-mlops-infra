# ---------------------------
# DYNAMODB QUERY HELPER
# ---------------------------

import boto3
import pandas as pd
import logging


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


dynamodb_client = boto3.client('dynamodb', region_name='eu-central-1')

def query_flights_by_time_window(start_timestamp: int, end_timestamp: int) -> pd.DataFrame:
    """
    Query flights from DynamoDB GSI within time window.
    
    Args:
        start_timestamp: Start of time window (Unix timestamp)
        end_timestamp: End of time window (Unix timestamp)
    
    Returns:
        Pandas DataFrame with predicted flights only (dep_delay not null)
    """
    try:
        logger.info(f"🔍 Querying DynamoDB: {start_timestamp} -> {end_timestamp} (window: {end_timestamp - start_timestamp}s)")
        
        response = dynamodb_client.query(
            TableName='raw-flights',
            IndexName='FlightsByTime',
            KeyConditionExpression='data_type = :pk AND #ts BETWEEN :start AND :end',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={
                ':pk': {'S': 'FLIGHTS'},
                ':start': {'N': str(start_timestamp)},
                ':end': {'N': str(end_timestamp)}
            }
        )
        
        items = response.get('Items', [])
        logger.info(f"✅ Retrieved {len(items)} items from DynamoDB")
        
        if not items:
            logger.warning("⚠️  No items found in time window")
            return pd.DataFrame()
        
        # Parse DynamoDB items to Python dict
        parsed_items = []
        for item in items:
            parsed = {}
            for key, value in item.items():
                if 'S' in value:
                    parsed[key] = value['S']
                elif 'N' in value:
                    parsed[key] = float(value['N'])
                elif 'NULL' in value:
                    parsed[key] = None
            parsed_items.append(parsed)
        
        # Create DataFrame
        df = pd.DataFrame(parsed_items)
        
        # ✅ Filter only predicted flights (dep_delay is not NULL)
        df_predicted = df[df['dep_delay'].notna()]
        logger.info(f"📊 After filtering predicted flights: {len(df_predicted)} records (filtered out {len(df) - len(df_predicted)} unpredicted)")
        
        return df_predicted
        
    except Exception as e:
        logger.error(f"❌ DynamoDB query error: {str(e)}", exc_info=True)
        return pd.DataFrame()