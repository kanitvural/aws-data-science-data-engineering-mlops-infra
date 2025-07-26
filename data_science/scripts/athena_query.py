import boto3
import time
import os
import pandas as pd

ATHENA_DB = os.environ["ATHENA_DB"]
TABLE_NAME = os.environ["TABLE_NAME"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
DEST_BUCKET = os.environ["DEST_BUCKET"] 
QUERY = f"SELECT * FROM {TABLE_NAME} LIMIT 100"

athena = boto3.client("athena")
s3 = boto3.client("s3")

# 1. Query Başlat
response = athena.start_query_execution(
    QueryString=QUERY,
    QueryExecutionContext={"Database": ATHENA_DB},
    ResultConfiguration={"OutputLocation": OUTPUT_BUCKET},
)
query_id = response["QueryExecutionId"]

# 2. Query tamamlanana kadar bekle
while True:
    result = athena.get_query_execution(QueryExecutionId=query_id)
    state = result["QueryExecution"]["Status"]["State"]
    if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
        break
    time.sleep(2)

# 3. Sonuç dosyasını al ve DataScience bucket'ına kopyala
output_key = f"query-results/{query_id}.csv"
temp_path = "/tmp/sample.csv"
s3.download_file(OUTPUT_BUCKET.split("/")[2], f"query-results/{query_id}.csv", temp_path)

# 4. CSV'yi hedef bucket'a yükle
s3.upload_file(temp_path, DEST_BUCKET.split("/")[2], "/".join(DEST_BUCKET.split("/")[3:]))

print("Athena query executed and sample data copied.")
