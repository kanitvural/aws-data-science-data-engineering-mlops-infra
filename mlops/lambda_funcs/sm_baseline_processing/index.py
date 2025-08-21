import boto3
import os
import json
import datetime
import logging
from sagemaker.processing import ScriptProcessor, ProcessingInput, ProcessingOutput
from sagemaker import Session

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
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = f"{project_name}-baseline-{timestamp}"

    logger.info(f"Starting baseline processing job: {job_name}")

    session = Session()
    processor = ScriptProcessor(
        role=sagemaker_role_arn,
        image_uri=_get_baseline_container_uri(region),
        command=["python3"],
        instance_count=1,
        instance_type="ml.m5.xlarge",
        volume_size_in_gb=30,
        max_runtime_in_seconds=1800,
        sagemaker_session=session,
    )

    processor.run(
        inputs=[
            ProcessingInput(
                source=f"s3://{data_science_bucket}/{baseline_input_key}",
                destination="/opt/ml/processing/input/baseline_dataset_input",
            )
        ],
        outputs=[
            ProcessingOutput(
                source="/opt/ml/processing/output",
                destination=f"s3://{mlops_bucket}/{baseline_output_prefix}",
            )
        ],
        wait=True,
    )

    logger.info(f"Baseline processing job completed: {job_name}")

    return {"statusCode": 200, "body": json.dumps({"processingJobName": job_name})}
