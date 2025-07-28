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

# SQL Query for sampling - sadece gerekli kolonları seç, row_num ve group_size dahil etme
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

def main():
    try:
        logger.info("Starting Athena data sampling process")
        logger.info(f"Database: {GLUE_DB_NAME}, Table: {GLUE_TABLE_NAME}")
        
        # Clients
        athena = boto3.client("athena")
        s3 = boto3.client("s3")
        logger.info("AWS clients initialized successfully")

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

        # 2. Wait for the query to complete with proper error handling
        max_wait_time = 300  # 5 minutes timeout
        start_time = time.time()
        
        logger.info("Waiting for query completion...")
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > max_wait_time:
                logger.error(f"Query timeout after {max_wait_time} seconds. Stopping execution...")
                athena.stop_query_execution(QueryExecutionId=query_id)
                sys.exit(1)
                
            result = athena.get_query_execution(QueryExecutionId=query_id)
            state = result["QueryExecution"]["Status"]["State"]
            
            logger.info(f"Query status: {state} (elapsed: {elapsed_time:.1f}s)")
            
            if state == "SUCCEEDED":
                logger.info("Query completed successfully!")
                break
            elif state in ["FAILED", "CANCELLED"]:
                error_reason = result["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
                logger.error(f"Query failed with reason: {error_reason}")
                sys.exit(1)
            
            time.sleep(5)

        # 3. Download query result CSV from S3
        bucket = ATHENA_OUTPUT_BUCKET_NAME.split("/")[2]
        key = f"query-results/{query_id}.csv"
        
        logger.info(f"Downloading query result from s3://{bucket}/{key}")
        
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read()
        logger.info(f"Successfully downloaded {len(content)} bytes from S3")

        # 4. Load content into a DataFrame
        logger.info("Loading data into pandas DataFrame")
        df = pd.read_csv(io.BytesIO(content))
        logger.info(f"DataFrame created with {len(df)} rows and {len(df.columns)} columns")

        # ============ DATA TYPE CORRECTIONS ============
        
        # Convert DateTime columns to datetime format
        datetime_columns = ['dep_time', 'sched_dep_time', 'arr_time', 'sched_arr_time', 'date']
        for col in datetime_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
                logger.info(f"Converted {col} to datetime")
        
        # Keep date_string as string
        if 'date_string' in df.columns:
            df['date_string'] = df['date_string'].astype(str)
            logger.info("Ensured date_string is string type")
        
        # Keep distance as integer
        if 'distance' in df.columns:
            df['distance'] = df['distance'].astype('int64')
            logger.info("Converted distance to int64")

        # ============ COMPREHENSIVE SCIENTIFIC NOTATION FIXES ============
        
        # Fix float columns - round to 6 decimal places to prevent scientific notation
        float_columns = df.select_dtypes(include=['float64', 'float32']).columns
        for col in float_columns:
            df[col] = df[col].round(6)
            logger.info(f"Applied rounding to float column: {col}")
        
        # Ensure integer columns display properly
        int_columns = df.select_dtypes(include=['int64', 'int32']).columns
        for col in int_columns:
            # Ensure they stay as proper integers
            df[col] = df[col].astype('int64')
            logger.info(f"Ensured integer format for column: {col}")

        logger.info(f"Final DataFrame info:")
        logger.info(f"Shape: {df.shape}")
        logger.info(f"Columns: {df.columns.tolist()}")
        logger.info(f"Data types: {df.dtypes.to_dict()}")

        # Custom describe function to avoid scientific notation in logs
        def format_describe_output(desc_df):
            """Format describe output to avoid scientific notation"""
            formatted_desc = desc_df.copy()
            for col in formatted_desc.columns:
                if formatted_desc[col].dtype in ['float64', 'float32']:
                    formatted_desc[col] = formatted_desc[col].apply(lambda x: f"{x:.6f}" if pd.notnull(x) else x)
            return formatted_desc

        logger.info("Sample statistics (formatted to avoid scientific notation):")
        try:
            desc_output = format_describe_output(df.describe())
            logger.info(f"\n{desc_output}")
        except Exception as e:
            logger.warning(f"Could not format describe output: {e}")
            logger.info(f"\n{df.describe()}")

        # 5. Write DataFrame to CSV buffer with explicit formatting
        logger.info("Preparing data for upload")
        csv_buffer = io.StringIO()
        # Use explicit float_format to ensure no scientific notation in CSV
        df.to_csv(csv_buffer, index=False, float_format='%.6f')
        csv_buffer.seek(0)
        csv_size = len(csv_buffer.getvalue())
        logger.info(f"CSV buffer prepared with {csv_size} characters")

        # 6. Upload CSV to destination S3 bucket
        dest_bucket = DEST_BUCKET_NAME.split("/")[2]
        dest_key = "/".join(DEST_BUCKET_NAME.split("/")[3:])
        
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