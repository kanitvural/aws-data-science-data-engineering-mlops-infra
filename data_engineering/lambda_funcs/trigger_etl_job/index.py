import boto3
import os
import logging

# Log ayarları
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Ortam değişkeninden job adını al
GLUE_JOB_NAME = os.environ.get("GLUE_JOB_NAME")

def lambda_handler(event, context):
    glue = boto3.client("glue")
    try:
        response = glue.start_job_run(JobName=GLUE_JOB_NAME)
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
