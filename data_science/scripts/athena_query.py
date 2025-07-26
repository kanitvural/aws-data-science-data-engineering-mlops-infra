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

# Environment variables
GLUE_DB_NAME = os.environ["GLUE_DB_NAME"]
GLUE_TABLE_NAME = os.environ["GLUE_TABLE_NAME"]
ATHENA_OUTPUT_BUCKET_NAME = os.environ["ATHENA_OUTPUT_BUCKET_NAME"]
DEST_BUCKET_NAME = os.environ["DEST_BUCKET_NAME"]

# SQL Query for sampling (1 for collecting all data, 0.01 for 10% sample for big data)
QUERY = f"""
WITH numbered_rows AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY airline, route ORDER BY RAND()) AS row_num,
         COUNT(*) OVER (PARTITION BY airline, route) AS group_size
  FROM {GLUE_DB_NAME}.{GLUE_TABLE_NAME}
)
SELECT *
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
        max_wait_time = 300  # 5 dakika timeout
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

        # 5. Write DataFrame to CSV buffer
        logger.info("Preparing data for upload")
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
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
