import os
import boto3
import logging
import sys  

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    region = os.environ['REGION']
    project_name = os.environ['PROJECT_NAME']
    parameter_name = f"/{project_name}/latest-approved-model-arn"

    ssm_client = boto3.client("ssm", region_name=region)

    try:
        response = ssm_client.get_parameter(Name=parameter_name)
        model_package_arn = response['Parameter']['Value']
        logger.info(f"✅ Approved model found in SSM: {model_package_arn}")
        logger.info("🚀 Production deployment can proceed...")
        sys.exit(0) 
    except ssm_client.exceptions.ParameterNotFound:
        logger.error(f"❌ No approved model found in SSM at {parameter_name}")
        logger.error("💥 CodeBuild will FAIL because of missing parameter")
        sys.exit(1) 
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        sys.exit(1) 

if __name__ == "__main__":
    main()