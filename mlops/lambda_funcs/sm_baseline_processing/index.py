import boto3
import os
import json
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _get_baseline_container_uri(region: str) -> str:
    """Return AWS Model Monitor Analyzer container URI for the given region"""
    region_to_account = {
        "eu-north-1": "895015795356",
        "me-south-1": "607024016150",
        "ap-south-1": "126357580389",
        "eu-west-3": "680080141114",
        "us-east-2": "777275614652",
        "eu-west-1": "468650794304",
        "eu-central-1": "048819808253",
        "sa-east-1": "539772159869",
        "ap-east-1": "001633400207",
        "us-east-1": "156813124566",
        "ap-northeast-2": "709848358524",
        "eu-west-2": "749857470468",
        "ap-northeast-1": "574779866223",
        "us-west-2": "159807026194",
        "us-west-1": "890145073186",
        "ap-southeast-1": "245545462676",
        "ap-southeast-2": "563025443158",
        "ca-central-1": "536280801234",
    }
    account = region_to_account.get(region)
    if not account:
        raise ValueError(f"No baseline container for region {region}")
    return f"{account}.dkr.ecr.{region}.amazonaws.com/sagemaker-model-monitor-analyzer"


def lambda_handler(event, context):
    project_name = os.environ["PROJECT_NAME"]
    region = os.environ["REGION"]
    sagemaker_role_arn = os.environ["SAGEMAKER_ROLE_ARN"]
    baseline_input_key = os.environ["BASELINE_INPUT_KEY"]
    data_science_bucket = os.environ["DATA_SCIENCE_BUCKET"]
    mlops_bucket = os.environ["MLOPS_BUCKET"]
    baseline_output_prefix = os.environ["BASELINE_OUTPUT_PREFIX"]
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = f"{project_name}-baseline-{timestamp}"

    logger.info(f"Starting baseline processing job: {job_name}")

    # SageMaker client
    sagemaker_client = boto3.client('sagemaker', region_name=region)

    try:
        # Processing job parameters
        processing_job_request = {
            'ProcessingJobName': job_name,
            'ProcessingResources': {
                'ClusterConfig': {
                    'InstanceCount': 1,
                    'InstanceType': 'ml.m5.xlarge',
                    'VolumeSizeInGB': 30
                }
            },
            'StoppingCondition': {
                'MaxRuntimeInSeconds': 1800
            },
            'AppSpecification': {
                'ImageUri': _get_baseline_container_uri(region)
            },
            'Environment': {
                "dataset_format": '{"csv": {"header": true, "output_columns_position": "START"}}',
                "dataset_source": "/opt/ml/processing/input/baseline_dataset_input",
                "output_path": "/opt/ml/processing/output",
                "publish_cloudwatch_metrics": "Disabled"
            },
            'ProcessingInputs': [
                {
                    'InputName': 'baseline_dataset_input',
                    'AppManaged': False,
                    'S3Input': {
                        'S3Uri': f"s3://{data_science_bucket}/{baseline_input_key}",
                        'LocalPath': '/opt/ml/processing/input/baseline_dataset_input',
                        'S3DataType': 'S3Prefix',
                        'S3InputMode': 'File'
                    }
                }
            ],
            'ProcessingOutputConfig': {
                'Outputs': [
                    {
                        'OutputName': 'baseline_output',
                        'AppManaged': False,
                        'S3Output': {
                            'S3Uri': f"s3://{mlops_bucket}/{baseline_output_prefix}",
                            'LocalPath': '/opt/ml/processing/output',
                            'S3UploadMode': 'EndOfJob'
                        }
                    }
                ]
            },
            'RoleArn': sagemaker_role_arn
        }

        # Start Processing job
        response = sagemaker_client.create_processing_job(**processing_job_request)
        
        logger.info(f"Processing job started successfully: {job_name}")
        logger.info(f"Processing job ARN: {response.get('ProcessingJobArn', 'N/A')}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "processingJobName": job_name,
                "processingJobArn": response.get('ProcessingJobArn'),
                "message": "Baseline processing job started successfully"
            })
        }

    except Exception as e:
        logger.error(f"Error creating baseline processing job: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "message": "Failed to create baseline processing job"
            })
        }
