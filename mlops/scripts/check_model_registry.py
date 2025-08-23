import os
import boto3
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    region = os.environ['REGION']
    model_package_group_name = os.environ['MODEL_PACKAGE_GROUP_NAME']
    
    sagemaker_client = boto3.client('sagemaker', region_name=region)
    
    max_attempts = 10
    wait_seconds = 30
    
    logger.info(f"🔍 Searching for approved model: {model_package_group_name}")
    
    for attempt in range(max_attempts):
        try:
            response = sagemaker_client.list_model_packages(
                ModelPackageGroupName=model_package_group_name,
                ModelApprovalStatus='Approved',
                SortBy='CreationTime',
                SortOrder='Descending',
                MaxResults=1
            )
            
            models = response.get('ModelPackageSummaryList', [])
            
            if models:
                model = models[0]
                logger.info(f"✅ Approved model found: {model['ModelPackageArn']}")
                logger.info(f"📅 Created at: {model['CreationTime']}")
                logger.info("🚀 Production deployment can proceed...")
                return
                
            logger.warning(f"⏳ No approved model yet. Attempt {attempt + 1}/{max_attempts}")
            
            if attempt < max_attempts - 1:
                logger.info(f"🕒 Waiting {wait_seconds} seconds...")
                time.sleep(wait_seconds)
                
        except Exception as e:
            logger.warning(f"⚠️ Error (attempt {attempt + 1}): {str(e)}")
            if attempt < max_attempts - 1:
                time.sleep(wait_seconds)
    
    logger.error("❌ No approved model found after all attempts")
    raise Exception("No approved model found")

if __name__ == "__main__":
    main()