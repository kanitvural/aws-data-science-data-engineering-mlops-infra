import boto3
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


CRAWLER_NAME = os.environ.get("CRAWLER_NAME")

def lambda_handler(event, context):
    glue = boto3.client("glue")
    try:
        glue.start_crawler(Name=CRAWLER_NAME)
        logger.info(f"Crawler started: {CRAWLER_NAME}")
        return {
            "statusCode": 200,
            "body": f"Crawler started: {CRAWLER_NAME}"
        }
    except Exception as e:
        logger.error(f"Failed to start crawler: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }

