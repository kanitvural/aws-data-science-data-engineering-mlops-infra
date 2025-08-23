import os
import json
import logging
from datetime import datetime
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def lambda_handler(event, context):

    model_s3_uri = os.environ["MODEL_S3_URI"]
    image_uri = os.environ["INFERENCE_IMAGE_URI"]
    model_package_group_name = os.environ["MODEL_PACKAGE_GROUP_NAME"]
    evaluation_result_bucket = os.environ["EVALUATION_RESULT_S3_BUCKET"]
    evaluation_result_key = os.environ.get("EVALUATION_RESULT_KEY", "dev-endpoint-evaluation-result/evaluation.json")
    region = os.environ.get("REGION", "eu-central-1")
    project_name = os.environ.get("PROJECT_NAME", "mlops")

    # AWS clients
    s3_client = boto3.client("s3", region_name=region)
    sagemaker_client = boto3.client("sagemaker", region_name=region)
    ssm_client = boto3.client("ssm", region_name=region)

    try:
        # Model Package Group exists control
        try:
            sagemaker_client.describe_model_package_group(ModelPackageGroupName=model_package_group_name)
            logger.info(f"Model package group already exists: {model_package_group_name}")
        except Exception as mpg_error:
            logger.info(f"Creating model package group: {model_package_group_name}")
            sagemaker_client.create_model_package_group(
                ModelPackageGroupName=model_package_group_name,
                ModelPackageGroupDescription="MLOps model registry for flight delay prediction",
            )

        # Read Evaluation File
        logger.info(f"Reading evaluation results from s3://{evaluation_result_bucket}/{evaluation_result_key}")
        eval_obj = s3_client.get_object(Bucket=evaluation_result_bucket, Key=evaluation_result_key)
        evaluation_data = json.loads(eval_obj["Body"].read().decode("utf-8"))

        # Evaluation control
        if not evaluation_data.get("evaluation_passed", False):
            logger.error("Evaluation failed. Model registration skipped.")
            return {
                "statusCode": 400,
                "message": "Evaluation failed. Model not registered.",
                "evaluation_data": evaluation_data,
            }

        # Model register
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        model_package_name = f"{model_package_group_name}-{timestamp}"

        logger.info(f"Evaluation passed. Registering model package: {model_package_name}")

        # Model package create request
        create_model_package_request = {
            "ModelPackageGroupName": model_package_group_name,  # Sadece group name
            "ModelPackageDescription": f"Auto-registered model on {timestamp}",
            "ModelApprovalStatus": "Approved",
            "InferenceSpecification": {
                "Containers": [
                    {
                        "Image": image_uri,
                        "ModelDataUrl": model_s3_uri,
                    }
                ],
                "SupportedContentTypes": ["text/csv", "application/json"],
                "SupportedResponseMIMETypes": ["text/csv", "application/json"],
            },
            "ModelMetrics": {
                "ModelQuality": {
                    "Statistics": {
                        "ContentType": "application/json",
                        "S3Uri": f"s3://{evaluation_result_bucket}/{evaluation_result_key}",
                    }
                }
            },
        }

        # Create Model package
        response = sagemaker_client.create_model_package(**create_model_package_request)
        model_package_arn = response["ModelPackageArn"]

        logger.info(f"Model successfully registered: {model_package_arn}")

        # Store the Model Package ARN in SSM Parameter Store
        parameter_name = f"{project_name}/latest-approved-model-arn"

        ssm_client.put_parameter(
            Name=parameter_name,
            Value=model_package_arn,
            Type="String",
            Overwrite=True,
        )
        logger.info(f"Stored model package ARN in SSM Parameter Store: {parameter_name}")

        return {
            "statusCode": 200,
            "model_package_arn": model_package_arn,
            "message": "Model successfully registered",
            "evaluation_data": evaluation_data,
        }

    except Exception as e:
        logger.error(f"Error during model registration: {str(e)}")
        return {"statusCode": 500, "message": f"Model registration failed: {str(e)}"}
