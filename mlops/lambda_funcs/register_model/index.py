import json
import boto3
import logging
import os
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Registers model to SageMaker Model Registry as Approved
    
    Gets parameters from environment variables:
    - MODEL_PACKAGE_GROUP_NAME
    - MODEL_S3_URI
    - INFERENCE_IMAGE_URI
    - MODEL_DESCRIPTION (optional)
    - EVALUATION_RESULT_S3_BUCKET
    - EVALUATION_RESULT_KEY (optional, default: 'dev-endpoint-evaluation-result/evaluation.json')
    """
    
    try:
        # Get parameters from environment variables
        model_package_group_name = os.environ['MODEL_PACKAGE_GROUP_NAME']
        model_s3_uri = os.environ['MODEL_S3_URI']
        inference_image_uri = os.environ['INFERENCE_IMAGE_URI']
        model_description = os.environ.get('MODEL_DESCRIPTION', 'XGBoost model for flight delay prediction')
        evaluation_result_s3_bucket = os.environ['EVALUATION_RESULT_S3_BUCKET']
        evaluation_result_key = os.environ.get('EVALUATION_RESULT_KEY', 'dev-endpoint-evaluation-result/evaluation.json')
        
        # Create SageMaker client
        sagemaker_client = boto3.client('sagemaker')
        s3_client = boto3.client('s3')
        
        # Read evaluation results from S3
        logger.info(f"Reading evaluation results from S3: {evaluation_result_s3_bucket}/{evaluation_result_key}")
        eval_obj = s3_client.get_object(Bucket=evaluation_result_s3_bucket, Key=evaluation_result_key)
        evaluation_data = json.loads(eval_obj['Body'].read().decode('utf-8'))
        
        # Check if evaluation passed
        if not evaluation_data.get('evaluation_passed', False):
            logger.error("Evaluation did not pass. Model will not be registered.")
            return {
                'statusCode': 400,
                'message': 'Model evaluation failed. Registration skipped.',
                'evaluation_passed': False,
                'rmse': evaluation_data.get('rmse')
            }
        
        logger.info(f"Evaluation passed with RMSE: {evaluation_data.get('rmse')}")
        
        # Prepare model metrics for registry
        model_metrics = {
            "ModelQuality": {
                "Statistics": {
                    "ContentType": "application/json",
                    "S3Uri": f"s3://{evaluation_result_s3_bucket}/{evaluation_result_key}"
                }
            }
        }
        
        # Create model package
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        create_model_package_input = {
            "ModelPackageGroupName": model_package_group_name,
            "ModelPackageDescription": f"{model_description} - Registered on {timestamp}",
            "ModelApprovalStatus": "Approved",
            "InferenceSpecification": {
                "Containers": [
                    {
                        "Image": inference_image_uri,
                        "ModelDataUrl": model_s3_uri,
                    }
                ],
                "SupportedContentTypes": ["text/csv"],
                "SupportedResponseMIMETypes": ["text/csv"],
            },
            "ModelMetrics": model_metrics,
            "CustomerMetadataProperties": {
                "rmse": str(evaluation_data.get('rmse')),
                "threshold": str(evaluation_data.get('threshold')),
                "total_predictions": str(evaluation_data.get('total_predictions')),
                "registration_timestamp": timestamp
            }
        }
        
        logger.info("Creating model package in SageMaker Model Registry...")
        response = sagemaker_client.create_model_package(**create_model_package_input)
        
        model_package_arn = response["ModelPackageArn"]
        logger.info(f"Model package created successfully: {model_package_arn}")
        
        # Return success response
        return {
            'statusCode': 200,
            'model_package_arn': model_package_arn,
            'model_package_group_name': model_package_group_name,
            'approval_status': 'Approved',
            'rmse': evaluation_data.get('rmse'),
            'threshold': evaluation_data.get('threshold'),
            'registration_timestamp': timestamp,
            'message': 'Model successfully registered to Model Registry as Approved'
        }
        
    except Exception as e:
        logger.error(f"Model registration error: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'message': 'Model registration failed'
        }