import boto3
import pandas as pd
import json
import logging


# S3 Configuration
REGION = "eu-central-1"
MLOPS_BUCKET = "mlops-bucket-058264126563"
MLOPS_PREFIX = "predicted/flight-events/"

s3_client = boto3.client('s3', region_name=REGION)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def load_flight_data() -> pd.DataFrame:
    """Load all flight data from S3 and clean it."""
    predicted_data = []
    
    try:
        # Get all date prefixes
        resp = s3_client.list_objects_v2(Bucket=MLOPS_BUCKET, Prefix=MLOPS_PREFIX, Delimiter='/')
        dates = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]
        
        for date_prefix in dates:
            # Get all hour prefixes for this date
            resp_hours = s3_client.list_objects_v2(Bucket=MLOPS_BUCKET, Prefix=date_prefix, Delimiter='/')
            hours = [h['Prefix'] for h in resp_hours.get('CommonPrefixes', [])]
            
            for hour_prefix in hours:
                # Get all files in this hour
                resp_files = s3_client.list_objects_v2(Bucket=MLOPS_BUCKET, Prefix=hour_prefix)
                if 'Contents' not in resp_files:
                    continue
                    
                all_files = [obj['Key'] for obj in resp_files['Contents']]
                
                # Read each file
                for key in all_files:
                    obj = s3_client.get_object(Bucket=MLOPS_BUCKET, Key=key)
                    for line in obj['Body'].read().decode('utf-8').strip().split('\n'):
                        if line:
                            predicted_data.append(json.loads(line))
        
        # Create DataFrame
        df = pd.DataFrame(predicted_data)
        logger.info(f"✅ Loaded {len(df)} records")
        
        # Clean data (remove NaN rows)
        df_clean = df.dropna()
        logger.info(f"📊 Cleaned data: {len(df_clean)} records")
        
        # Select final columns
        final_columns = [
            "dep_time", "sched_dep_time", "dep_delay",
            "arr_time", "sched_arr_time", "arr_delay",
            "carrier", "flight", "tailnum", "origin", "dest",
            "air_time", "distance", "airline", "route",
            "temp", "dewp", "humid", "wind_dir", "wind_speed", "wind_gust",
            "precip", "pressure", "visib", "date"
        ]
        
        df_clean = df_clean[final_columns]
        return df_clean
        
    except Exception as e:
        logger.error(f"❌ Error loading data: {str(e)}")
        raise
