import boto3
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


crawler_name = os.environ.get("CRAWLER_NAME")

def lambda_handler(event, context):
    glue = boto3.client("glue")
    try:
        glue.start_crawler(Name=crawler_name)
        logger.info(f"Crawler started: {crawler_name}")
        return {
            "statusCode": 200,
            "body": f"Crawler started: {crawler_name}"
        }
    except Exception as e:
        logger.error(f"Failed to start crawler: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }

