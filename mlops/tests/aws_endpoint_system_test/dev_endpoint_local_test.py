import pandas as pd
import requests
import boto3
import json
import io
from sklearn.metrics import mean_squared_error
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Parameters
ENDPOINT_URL = "https://your-endpoint-url/invocations" 
TEST_DATA_S3_BUCKET = "data-science-bucket-058264126563"
EVALUATION_RESULT_S3_BUCKET = "mlops-bucket-058264126563"
TEST_CSV_KEY = "sagemaker-preprocess-output/test/test.csv"
TARGET_COLUMN = "dep_delay"
RMSE_THRESHOLD = 20.0


def main():
    # Read test data from S3
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=TEST_DATA_S3_BUCKET, Key=TEST_CSV_KEY)
    test_df = pd.read_csv(io.BytesIO(obj['Body'].read()))
    
    logger.info(f"Test data loaded: {len(test_df)} rows")
    
    # Separate target
    y_true = test_df[TARGET_COLUMN].values
    X_test = test_df.drop(columns=[TARGET_COLUMN])
    
    # Convert to CSV string
    csv_buffer = io.StringIO()
    X_test.to_csv(csv_buffer, header=False, index=False)
    csv_data = csv_buffer.getvalue()
    
    # Send to endpoint
    logger.info("Making predictions...")
    headers = {'Content-Type': 'text/csv'}
    response = requests.post(ENDPOINT_URL, data=csv_data, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"Error: {response.status_code} - {response.text}")
        return
    
    # Parse results
    predictions_df = pd.read_csv(io.StringIO(response.text), header=None)
    predictions = predictions_df.iloc[:, 0].values
    
    # Calculate RMSE
    rmse = np.sqrt(mean_squared_error(y_true, predictions))
    
    # Prepare results
    evaluation = {
        'rmse': float(rmse),
        'threshold': RMSE_THRESHOLD,
        'evaluation_passed': rmse < RMSE_THRESHOLD,
        'total_predictions': len(predictions)
    }
    
    # Save to S3
    s3.put_object(
        Bucket=EVALUATION_RESULT_S3_BUCKET,
        Key='dev-endpoint-evaluation-result/evaluation.json',
        Body=json.dumps(evaluation, indent=2)
    )
    
    logger.info(f"RMSE: {rmse:.4f}")
    logger.info(f"Threshold: {RMSE_THRESHOLD}")
    logger.info(f"Test {'PASSED' if rmse < RMSE_THRESHOLD else 'FAILED'}")
    logger.info("evaluation.json saved to S3")

if __name__ == "__main__":
    main()