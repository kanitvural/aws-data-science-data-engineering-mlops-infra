import boto3
import os
import math
import numpy as np
import pandas as pd
from datetime import datetime
from multiprocessing.pool import ThreadPool
from botocore.config import Config
from botocore.exceptions import ClientError

# Config
config = Config(retries={"max_attempts": 10, "mode": "adaptive"})
sagemaker = boto3.client("sagemaker-runtime", config=config, region_name="eu-central-1")
s3 = boto3.client("s3", region_name="eu-central-1")

# Endpoint and dataset info
endpoint_name = "mlops-prod-endpoint"
bucket_name = "data-science-bucket-058264126563"
s3_key = "sagemaker-preprocess-output/test/test.csv"


def predict(payload):
    """
    Send a single record to the SageMaker endpoint.
    """
    payload = ",".join(map(str, payload))
    try:
        response = sagemaker.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="text/csv",
            Body=payload
        )
        return response["Body"].read().decode("utf-8").rstrip("\n")
    except ClientError as e:
        print("Invoke error:", e.response["Error"]["Message"])
        return None


def run_test(max_threads, max_requests, dataset):
    """
    Perform load testing by sending parallel requests to the endpoint.
    """
    start_time = datetime.now()
    num_batches = math.ceil(max_requests / len(dataset))

    # Replicate test dataset to reach the desired request count
    requests = []
    for _ in range(num_batches):
        batch = dataset.copy()
        np.random.shuffle(batch)
        requests += batch.tolist()

    # Send parallel requests
    pool = ThreadPool(max_threads)
    results = pool.map(predict, requests[:max_requests])
    pool.close()
    pool.join()

    elapsed_time = datetime.now() - start_time
    print(f"Total requests: {max_requests}")
    print(f"Parallel threads: {max_threads}")
    print(f"Elapsed time: {elapsed_time}")
    print(f"Average latency (s/request): {elapsed_time.total_seconds() / max_requests:.6f}")


if __name__ == "__main__":
    # Download dataset if not present locally
    local_file = "test.csv"
    if not os.path.exists(local_file):
        print("Downloading test dataset from S3...")
        s3.download_file(bucket_name, s3_key, local_file)

    # Prepare dataset
    test_data = pd.read_csv(local_file, header=None)
    test_data = test_data.drop(test_data.columns[0], axis=1)  # drop first column (ID/label)

    # Convert all columns to numeric (force casting)
    test_data = test_data.apply(pd.to_numeric, errors="coerce")
    test_data = test_data.fillna(0)  # replace NaN with 0

    dataset = test_data.to_numpy()

    print("Starting load test...")
    run_test(max_threads=150, max_requests=100000, dataset=dataset)
