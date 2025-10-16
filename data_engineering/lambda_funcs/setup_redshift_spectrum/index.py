import json
import boto3
import time
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

redshift_data = boto3.client('redshift-data')
secretsmanager = boto3.client('secretsmanager')
sns = boto3.client('sns')


def send_sns_notification(topic_arn, subject, message):
    try:
        sns.publish(TopicArn=topic_arn, Subject=subject, Message=message)
        logger.info(f"SNS notification sent")
    except Exception as e:
        logger.error(f"SNS error: {e}")


def lambda_handler(event, context):
    request_type = event.get('RequestType', 'Create')
    
    if request_type == 'Delete':
        return {'PhysicalResourceId': 'spectrum-setup', 'Data': {'Message': 'Deleted'}}
    
    if request_type not in ['Create', 'Update']:
        return {'PhysicalResourceId': 'spectrum-setup', 'Data': {'Message': 'Skipped'}}
    
    try:
        workgroup_name = os.environ['WORKGROUP_NAME']
        database_name = os.environ['DATABASE_NAME']
        glue_database = os.environ['GLUE_DATABASE']
        iam_role_arn = os.environ['IAM_ROLE_ARN']
        region = os.environ['REGION']
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        redshift_endpoint = os.environ.get('REDSHIFT_ENDPOINT', 'N/A')
        secret_arn = os.environ['SECRET_ARN']
        
        logger.info(f"Setting up Spectrum for: {workgroup_name}")
        time.sleep(30)
        
        sql = f"""
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE '{glue_database}'
IAM_ROLE '{iam_role_arn}'
REGION '{region}';
"""
        
        # Redshift Serverless: Only WorkgroupName + Database needed
        response = redshift_data.execute_statement(
            WorkgroupName=workgroup_name,
            Database=database_name,
            Sql=sql
        )
        
        statement_id = response['Id']
        logger.info(f"Statement ID: {statement_id}")
        
        # Wait for completion
        for _ in range(24):  # 2 minutes max
            status_resp = redshift_data.describe_statement(Id=statement_id)
            status = status_resp['Status']
            logger.info(f"Status: {status}")
            
            if status == 'FINISHED':
                logger.info("✅ Spectrum setup successful")
                
                if sns_topic_arn:
                    secret_name = secret_arn.split('/')[-1]
                    msg = f"""✅ Redshift Serverless + Spectrum Ready!

📊 Connection Info:
  Endpoint: {redshift_endpoint}
  Port: 5439
  Database: {database_name}
  Username: admin
  Schema: spectrum

🔐 Get Password:
aws secretsmanager get-secret-value --secret-id {secret_name} --query SecretString --output text | jq -r .password

💻 Test Query:
SELECT * FROM spectrum.flight_events LIMIT 10;

📊 PowerBI:
  Server: {redshift_endpoint}
  Database: {database_name}
  Mode: DirectQuery
"""
                    send_sns_notification(sns_topic_arn, "✅ Redshift Spectrum Ready", msg)
                
                return {
                    'PhysicalResourceId': 'spectrum-setup',
                    'Data': {'Message': 'Success', 'StatementId': statement_id}
                }
                
            elif status in ['FAILED', 'ABORTED']:
                error = status_resp.get('Error', 'Unknown')
                logger.error(f"Failed: {error}")
                
                if 'already exists' in error.lower():
                    logger.info("Schema exists - OK")
                    return {
                        'PhysicalResourceId': 'spectrum-setup',
                        'Data': {'Message': 'Already exists'}
                    }
                
                if sns_topic_arn:
                    secret_name = secret_arn.split('/')[-1]
                    err_msg = f"""⚠️ Redshift Spectrum Setup Issue

Error: {error}

Manual fix - Run in Query Editor v2:
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE '{glue_database}'
IAM_ROLE '{iam_role_arn}'
REGION '{region}';

Get password:
aws secretsmanager get-secret-value --secret-id {secret_name} --query SecretString --output text | jq -r .password
"""
                    send_sns_notification(sns_topic_arn, "⚠️ Redshift Spectrum Needs Attention", err_msg)
                
                return {
                    'PhysicalResourceId': 'spectrum-setup',
                    'Data': {'Message': f'Failed: {error}'}
                }
            
            time.sleep(5)
        
        logger.warning("Timeout")
        return {
            'PhysicalResourceId': 'spectrum-setup',
            'Data': {'Message': 'Timeout'}
        }
        
    except Exception as e:
        logger.error(f"Exception: {e}")
        return {
            'PhysicalResourceId': 'spectrum-setup',
            'Data': {'Message': f'Error: {str(e)}'}
        }