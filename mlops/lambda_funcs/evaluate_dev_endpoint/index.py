import json
import boto3
import pandas as pd
import numpy as np
import io
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def lambda_handler(event, context):
    """
    Gets parameters from environment variables:
    - ENDPOINT_NAME
    - TEST_DATA_S3_BUCKET
    - EVALUATION_RESULT_S3_BUCKET
    - TEST_CSV_KEY
    - TARGET_COLUMN (optional, default: 'target')
    - RMSE_THRESHOLD (optional, default: 20.0)
    """
    
    try:
        # Get parameters from environment variables
        endpoint_name = os.environ['ENDPOINT_NAME']
        test_data_s3_bucket = os.environ['TEST_DATA_S3_BUCKET']
        evaluation_result_s3_bucket = os.environ['EVALUATION_RESULT_S3_BUCKET']
        test_csv_key = os.environ['TEST_CSV_KEY']
        target_column = os.environ.get('TARGET_COLUMN', 'target')
        rmse_threshold = float(os.environ.get('RMSE_THRESHOLD', '20.0'))
        
        # Read test data from S3
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket=test_data_s3_bucket, Key=test_csv_key)
        test_df = pd.read_csv(io.BytesIO(obj['Body'].read()))
        logger.info(f"Test data loaded: {len(test_df)} rows")
        
        # Separate target
        y_true = test_df[target_column].values
        X_test = test_df.drop(columns=[target_column])
        
        # Convert to CSV string
        csv_buffer = io.StringIO()
        X_test.to_csv(csv_buffer, header=False, index=False)
        csv_data = csv_buffer.getvalue()
        
        # Send to SageMaker endpoint using boto3
        logger.info("Making predictions...")
        sagemaker_runtime = boto3.client('sagemaker-runtime')
        
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='text/csv',
            Body=csv_data
        )
        
        # Parse results
        result = response['Body'].read().decode('utf-8')
        predictions_df = pd.read_csv(io.StringIO(result), header=None)
        predictions = predictions_df.iloc[:, 0].values
        
        # Calculate RMSE manually (without sklearn)
        mse = np.mean((y_true - predictions) ** 2)
        rmse = float(np.sqrt(mse))
        logger.info(f"RMSE calculated: {rmse:.4f}")
        
        # Evaluation result
        evaluation = {
            'rmse': rmse,
            'threshold': rmse_threshold,
            'evaluation_passed': rmse < rmse_threshold,
            'total_predictions': len(predictions)
        }
        
        # Save to S3
        s3.put_object(
            Bucket=evaluation_result_s3_bucket,
            Key='dev-endpoint-evaluation-result/evaluation.json',
            Body=json.dumps(evaluation, indent=2)
        )
        logger.info("evaluation.json saved to S3")
        logger.info(f"RMSE: {rmse:.4f}")
        logger.info(f"Threshold: {rmse_threshold}")
        logger.info(f"Test {'PASSED' if rmse < rmse_threshold else 'FAILED'}")
        
        # Response for direct invocation
        return {
            'statusCode': 200,
            'evaluation_passed': evaluation['evaluation_passed'],
            'rmse': rmse,
            'threshold': rmse_threshold,
            'message': 'Evaluation completed successfully'
        }
        
    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e)
        }
