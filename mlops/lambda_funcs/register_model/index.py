import os
import json
import logging
from datetime import datetime
import boto3
import sagemaker
from sagemaker.model import Model
from sagemaker import Session

# Logging ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def lambda_handler(event, context):
    # Çevresel değişkenler
    model_s3_uri = os.environ['MODEL_S3_URI']
    image_uri = os.environ['INFERENCE_IMAGE_URI']
    model_package_group_name = os.environ['MODEL_PACKAGE_GROUP_NAME']
    evaluation_result_bucket = os.environ['EVALUATION_RESULT_S3_BUCKET']
    evaluation_result_key = os.environ.get('EVALUATION_RESULT_KEY', 'dev-endpoint-evaluation-result/evaluation.json')
    role = os.environ['SAGEMAKER_ROLE_ARN']

    # SageMaker Session
    sagemaker_session = Session()

    # S3 client doğrudan boto3 ile
    s3_client = boto3.client('s3')

    # Evaluation dosyasını oku
    logger.info(f"Reading evaluation results from s3://{evaluation_result_bucket}/{evaluation_result_key}")
    eval_obj = s3_client.get_object(Bucket=evaluation_result_bucket, Key=evaluation_result_key)
    evaluation_data = json.loads(eval_obj['Body'].read().decode('utf-8'))

    # Evaluation kontrolü
    if not evaluation_data.get('evaluation_passed', False):
        logger.error("Evaluation failed. Model registration skipped.")
        return {
            "statusCode": 400,
            "message": "Evaluation failed. Model not registered.",
            "evaluation_data": evaluation_data
        }

    # Model register işlemi
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    logger.info(f"Evaluation passed. Registering model at {timestamp}")

    model = Model(
        image_uri=image_uri,
        model_data=model_s3_uri,
        role=role,
        sagemaker_session=sagemaker_session
    )

    response = model.register(
        model_package_group_name=model_package_group_name,
        model_metrics={
            "ModelQuality": {
                "Statistics": {
                    "ContentType": "application/json",
                    "S3Uri": f"s3://{evaluation_result_bucket}/{evaluation_result_key}"
                }
            }
        },
        approval_status='Approved',
        description=f"Registered on {timestamp}",
    )

    logger.info(f"Model successfully registered: {response.model_package_arn}")

    return {
        "statusCode": 200,
        "model_package_arn": response.model_package_arn,
        "message": "Model successfully registered"
    }
