import boto3
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


glue_job_name = os.environ["GLUE_JOB_NAME"]
region = os.environ["REGION"]
glue_client = boto3.client("glue",region_name = region)

def lambda_handler(event, context):

    try:
        response = glue_client.start_job_run(JobName=glue_job_name)
        logger.info(f"Glue job started: {response['JobRunId']}")
        return {
            'statusCode': 200,
            'body': f"Glue job started: {response['JobRunId']}"
        }
    except Exception as e:
        logger.error(f"Failed to start Glue job: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
