import boto3
import time
import os
import pandas as pd
import io
import sys
import logging
from botocore.exceptions import ClientError, BotoCoreError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Pandas display options to avoid scientific notation for ALL numeric types
pd.set_option('display.float_format', '{:.6f}'.format)
pd.set_option('display.precision', 6)
pd.options.display.float_format = '{:.6f}'.format

# Environment variables
GLUE_DB_NAME = os.environ["GLUE_DB_NAME"]
GLUE_TABLE_NAME = os.environ["GLUE_TABLE_NAME"]
ATHENA_OUTPUT_BUCKET_NAME = os.environ["ATHENA_OUTPUT_BUCKET_NAME"]
DEST_BUCKET_NAME = os.environ["DEST_BUCKET_NAME"]
REGION = os.environ["REGION"]
RETRAIN_DATA_PATH = os.environ["RETRAIN_DATA_PATH"]

# SQL Query for sampling 
QUERY = f"""
WITH numbered_rows AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY airline, route ORDER BY RAND()) AS row_num,
         COUNT(*) OVER (PARTITION BY airline, route) AS group_size
  FROM {GLUE_DB_NAME}.{GLUE_TABLE_NAME}
)
SELECT year, month, day, dep_time, sched_dep_time, dep_delay,
       arr_time, sched_arr_time, arr_delay, carrier, flight,
       tailnum, origin, dest, air_time, distance, hour, minute,
       airline, route, temp, dewp, humid, wind_dir, wind_speed,
       wind_gust, precip, pressure, visib, date, date_string
FROM numbered_rows
WHERE row_num <= CEIL(group_size * 1);
"""

def check_retrain_data_exists(s3_client, bucket, key):
    """Check if retrain data exists in S3"""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        else:
            raise e

def load_retrain_csv(s3_client, bucket, key):
    """Load retrain CSV from S3"""
    logger.info(f"Loading retrain data from s3://{bucket}/{key}")
    
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()
    
    df = pd.read_csv(io.BytesIO(content))
    logger.info(f"Retrain data loaded: {len(df)} rows, {len(df.columns)} columns")
    
    return df

def delete_retrain_file(s3_client, bucket, key):
    """Delete retrain file from S3 after processing"""
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        logger.info(f"✅ Retrain file deleted: s3://{bucket}/{key}")
    except Exception as e:
        logger.warning(f"Could not delete retrain file: {e}")

def get_athena_sample():
    """Get sample data from Athena (original logic)"""
    logger.info("Getting Athena sample data")
    
    # Clients
    athena = boto3.client("athena", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    
    # 1. Start Athena query execution
    logger.info("Starting Athena query execution")
    response = athena.start_query_execution(
        QueryString=QUERY,
        QueryExecutionContext={"Database": GLUE_DB_NAME},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_BUCKET_NAME},
        WorkGroup="primary"
    )
    query_id = response["QueryExecutionId"]
    logger.info(f"Query started successfully with ID: {query_id}")

    # 2. Wait for the query to complete
    max_wait_time = 300  # 5 minutes timeout
    start_time = time.time()
    
    logger.info("Waiting for query completion...")
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > max_wait_time:
            logger.error(f"Query timeout after {max_wait_time} seconds. Stopping execution...")
            athena.stop_query_execution(QueryExecutionId=query_id)
            raise Exception("Athena query timeout")
            
        result = athena.get_query_execution(QueryExecutionId=query_id)
        state = result["QueryExecution"]["Status"]["State"]
        
        logger.info(f"Query status: {state} (elapsed: {elapsed_time:.1f}s)")
        
        if state == "SUCCEEDED":
            logger.info("Query completed successfully!")
            break
        elif state in ["FAILED", "CANCELLED"]:
            error_reason = result["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
            raise Exception(f"Query failed with reason: {error_reason}")
        
        time.sleep(5)

    # 3. Download query result CSV from S3
    bucket = ATHENA_OUTPUT_BUCKET_NAME.split("/")[2]
    key = f"query-results/{query_id}.csv"
    
    logger.info(f"Downloading query result from s3://{bucket}/{key}")
    
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()
    logger.info(f"Successfully downloaded {len(content)} bytes from S3")

    # 4. Load content into DataFrame
    logger.info("Loading Athena data into pandas DataFrame")
    df = pd.read_csv(io.BytesIO(content))
    df['distance'] = df['distance'].astype(int)
    
    logger.info(f"Athena DataFrame created with {len(df)} rows and {len(df.columns)} columns")
    return df

def main():
    try:
        logger.info("Starting Athena data sampling process")
        logger.info(f"Database: {GLUE_DB_NAME}, Table: {GLUE_TABLE_NAME}")
        
        s3 = boto3.client("s3", region_name=REGION)
        
        # Parse destination bucket info
        dest_bucket = DEST_BUCKET_NAME.split("/")[2]
        dest_key = "/".join(DEST_BUCKET_NAME.split("/")[3:])
        
        # Check if retrain data exists
        retrain_exists = check_retrain_data_exists(s3, dest_bucket, RETRAIN_DATA_PATH)
        
        if retrain_exists:
            logger.info("🔄 RETRAIN MODE: Found retrain data, combining with Athena sample")
            
            try:
                # 1. Get Athena sample
                athena_df = get_athena_sample()
                
                # 2. Load and clean retrain data
                retrain_df = load_retrain_csv(s3, dest_bucket, RETRAIN_DATA_PATH)
                
                # 3. Combine and shuffle
                logger.info("Combining Athena sample with retrain data")
                combined_df = pd.concat([athena_df, retrain_df], ignore_index=True)
                final_df = combined_df.sample(frac=1).reset_index(drop=True)
                
                logger.info(f"Combined dataset: {len(final_df)} rows, {len(final_df.columns)} columns")
                logger.info(f"  - Athena sample: {len(athena_df)} rows")
                logger.info(f"  - Retrain data: {len(retrain_df)} rows")
                
                # 4. Cleanup retrain file
                delete_retrain_file(s3, dest_bucket, RETRAIN_DATA_PATH)
                
            except Exception as e:
                logger.error(f"Error in retrain logic: {e}")
                logger.info("Falling back to normal Athena sampling")
                final_df = get_athena_sample()
        else:
            logger.info("📊 BASELINE MODE: Using normal Athena sampling")
            final_df = get_athena_sample()

        # Upload final dataset
        logger.info("Preparing final data for upload")
        csv_buffer = io.StringIO()
        final_df.to_csv(csv_buffer, index=False, float_format='%.6f')
        csv_buffer.seek(0)
        csv_size = len(csv_buffer.getvalue())
        logger.info(f"CSV buffer prepared with {csv_size} characters")

        logger.info(f"Uploading processed data to s3://{dest_bucket}/{dest_key}")
        s3.put_object(
            Bucket=dest_bucket, 
            Key=dest_key, 
            Body=csv_buffer.getvalue(),
            ContentType='text/csv'
        )

        logger.info("✅ Athena data sampling and upload completed successfully!")
        
    except ClientError as e:
        logger.error(f"AWS service error: {e.response['Error']['Message']}")
        sys.exit(1)
    except BotoCoreError as e:
        logger.error(f"AWS SDK error: {str(e)}")
        sys.exit(1)
    except pd.errors.EmptyDataError:
        logger.error("No data returned from Athena query")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()