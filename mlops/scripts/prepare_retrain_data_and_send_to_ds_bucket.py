import os
import boto3
import pandas as pd
import logging
import json



# S3 paths from environment variables
region = os.environ["REGION"]
mlops_bucket = os.environ["BUCKET"]
mlops_prefix = os.environ["MLOPS_PREFIX"]

data_science_bucket = os.environ["DATA_SCIENCE_BUCKET"]
data_science_prefix = os.environ["DATA_SCIENCE_PREFIX"]
data_science_path = f"s3://{data_science_bucket}/{data_science_prefix}"


s3_client = boto3.client('s3', region_name=region)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# Prepare features for RETRAIN
# =============================================================================

predicted_data = []

resp = s3_client.list_objects_v2(Bucket=mlops_bucket, Prefix=mlops_prefix, Delimiter='/')
dates = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]

for date_prefix in dates:
    
    resp_hours = s3_client.list_objects_v2(Bucket=mlops_bucket, Prefix=date_prefix, Delimiter='/')
    hours = [h['Prefix'] for h in resp_hours.get('CommonPrefixes', [])]

    for hour_prefix in hours:
        resp_files = s3_client.list_objects_v2(Bucket=mlops_bucket, Prefix=hour_prefix)
        if 'Contents' not in resp_files:
            continue
        all_files = [obj['Key'] for obj in resp_files['Contents']]
        logger.info(f"📁 Found {len(all_files)} files")

        for key in all_files:
            obj = s3_client.get_object(Bucket=mlops_bucket, Key=key)
            for line in obj['Body'].read().decode('utf-8').strip().split('\n'):
                if line:
                    predicted_data.append(json.loads(line))

df_predicted = pd.DataFrame(predicted_data)
logger.info(f"✅ Loaded {len(df_predicted)} records")
logger.info(f"Sample columns: {list(df_predicted.columns)}")
logger.info(f"Columns Length: {len(df_predicted.columns)}")

# Clean data (remove NaN rows)
df_clean = df_predicted.dropna()
logger.info(f"📊 Cleaned data: {len(df_clean)} records (removed {len(df_predicted) - len(df_clean)} NaN rows)")

# Define the target column order (Athena sample schema)
final_columns = [
    "year", "month", "day",
    "dep_time", "sched_dep_time", "dep_delay",
    "arr_time", "sched_arr_time", "arr_delay",
    "carrier", "flight", "tailnum", "origin", "dest",
    "air_time", "distance", "hour", "minute",
    "airline", "route",
    "temp", "dewp", "humid", "wind_dir", "wind_speed", "wind_gust",
    "precip", "pressure", "visib",
    "date", "date_string"
]

# Keep only those columns, in the correct order
df_clean = df_clean[final_columns]

logger.info("✅ Columns aligned to Athena schema for future joins")
logger.info(f"Columns in order: {list(df_clean.columns)}")

# Save processed data to S3
df_clean.to_csv(data_science_path, index=False)
logger.info(f"💾 Processed data saved to: {data_science_path}")
