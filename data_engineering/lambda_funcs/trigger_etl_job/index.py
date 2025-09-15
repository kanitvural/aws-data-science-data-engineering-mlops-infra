import boto3
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


glue_job_name = os.environ.get("GLUE_JOB_NAME")

def lambda_handler(event, context):
    glue = boto3.client("glue")
    try:
        response = glue.start_job_run(JobName=glue_job_name)
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
