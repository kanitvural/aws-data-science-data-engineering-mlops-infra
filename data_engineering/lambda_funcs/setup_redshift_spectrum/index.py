import json
import boto3
import time
import os
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

workgroup_name = os.environ["WORKGROUP_NAME"]
glue_database = os.environ["GLUE_DATABASE"]
iam_role_arn = os.environ["IAM_ROLE_ARN"]
secret_arn = os.environ["SECRET_ARN"]
region = os.environ["REGION"]
sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
redshift_endpoint = os.environ.get("REDSHIFT_ENDPOINT", "N/A")
database_name = os.environ['DATABASE_NAME']

redshift_data = boto3.client("redshift-data", region_name=region)
secretsmanager = boto3.client("secretsmanager", region_name=region)
sns = boto3.client("sns", region_name=region)


def get_db_credentials(secret_arn):
    """
    Retrieve Redshift credentials from Secrets Manager
    """
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response["SecretString"])
        return secret.get("username"), secret.get("password")
    except ClientError as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise


def send_sns_notification(topic_arn, subject, message):
    """
    Send SNS notification with deployment details
    """
    try:
        response = sns.publish(TopicArn=topic_arn, Subject=subject, Message=message)
        logger.info(f"SNS sent. MessageId: {response['MessageId']}")
        return response
    except Exception as e:
        logger.error(f"Error sending SNS notification: {str(e)}")
        raise


def execute_sql_with_wait(sql, description):
    """
    Execute SQL and wait for completion
    """
    logger.info(f"Executing: {description}")
    
    # connect with admin credentials using SecretArn.
    response = redshift_data.execute_statement(
        WorkgroupName=workgroup_name,
        SecretArn=secret_arn,  # ✅ Admin user authentication
        Sql=sql,
    )
    
    statement_id = response["Id"]
    logger.info(f"Statement ID: {statement_id}")
    
    # Wait for completion
    max_wait = 120
    elapsed = 0
    
    while elapsed < max_wait:
        status_response = redshift_data.describe_statement(Id=statement_id)
        status = status_response["Status"]
        
        if status == "FINISHED":
            logger.info(f"✅ {description} - SUCCESS")
            return statement_id, status, None
        elif status in ["FAILED", "ABORTED"]:
            error = status_response.get("Error", "Unknown error")
            logger.error(f"❌ {description} - FAILED: {error}")
            return statement_id, status, error
        
        time.sleep(5)
        elapsed += 5
    
    logger.warning(f"⚠️ {description} - TIMEOUT")
    return statement_id, "TIMEOUT", "Statement execution timeout"


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")
    
    request_type = event.get("RequestType", "Create")
    
    if request_type == "Delete":
        logger.info("Delete request - no action needed")
        return {"PhysicalResourceId": "spectrum-setup", "Data": {"Message": "Deleted"}}
    
    try:
        # Get credentials for notification only
        username, password = get_db_credentials(secret_arn)
        logger.info(f"Retrieved credentials for user: {username}")
        
        # Wait for Redshift to be ready
        logger.info("Waiting 60 seconds for Redshift Serverless to be fully ready...")
        time.sleep(60)
        
        # Create external schema
        create_schema_sql = f"""
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE '{glue_database}'
IAM_ROLE '{iam_role_arn}'
REGION '{region}';
        """
        
        statement_id, status, error = execute_sql_with_wait(
            create_schema_sql, 
            "CREATE EXTERNAL SCHEMA spectrum"
        )
        
        # Prepare notification
        if status == "FINISHED":
            notification_subject = "✅ Redshift Spectrum Deployment Complete"
            notification_status = "SUCCESS ✅"
        else:
            notification_subject = "⚠️ Redshift Spectrum Deployment Issue"
            notification_status = f"FAILED ❌\nError: {error}"
        
        # Send SNS notification
        if sns_topic_arn:
            message = f"""
🎉 Redshift Serverless + Spectrum Deployment Status

✅ CONNECTION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoint:  {redshift_endpoint}
  Port:      5439
  Workgroup: {workgroup_name}

📊 POWERBI CONNECTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Server:   {redshift_endpoint}
  Port:     5439
  Database: {database_name}
  Username: {username}
  Password: {password}
  
  ⚠️ Use DirectQuery mode, NOT Import!

📝 TEST QUERIES (Run in Query Editor v2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  -- Check external schemas
  SELECT * FROM svv_external_schemas;
  
  -- List external tables
  SELECT * FROM svv_external_tables WHERE schemaname = 'spectrum';
  
  -- Query flight data
  SELECT COUNT(*) FROM spectrum.flight_events;
  
  -- Analyze delays by carrier
  SELECT carrier, AVG(dep_delay) AS avg_delay
  FROM spectrum.flight_events 
  WHERE dep_delay IS NOT NULL 
  GROUP BY carrier
  ORDER BY avg_delay DESC;

💰 COST INFO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Base Capacity: 8 RPU (~$3.60/hour when active)
  Auto-pause:    5 minutes of inactivity
  Free Tier:     First 300 RPU-hours FREE

✅ DEPLOYMENT STATUS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Statement ID: {statement_id}
  Status:       {notification_status}
  Schema:       spectrum → {glue_database}

🎊 Your data analytics infrastructure is ready!
            """
            
            try:
                send_sns_notification(sns_topic_arn, notification_subject, message)
                logger.info("✅ SNS notification sent successfully")
            except Exception as sns_error:
                logger.error(f"❌ Failed to send SNS: {str(sns_error)}")
        
        return {
            "PhysicalResourceId": "spectrum-setup",
            "Data": {
                "Message": "Spectrum setup completed",
                "StatementId": statement_id,
                "Status": status,
                "Error": error,
                "GlueDatabase": glue_database,
                "Endpoint": redshift_endpoint,
                "Username": username,
            },
        }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Exception: {error_msg}", exc_info=True)
        
        if sns_topic_arn:
            try:
                send_sns_notification(
                    sns_topic_arn,
                    "❌ Redshift Spectrum Setup Exception",
                    f"Error: {error_msg}\n\nCheck CloudWatch logs: /aws/lambda/{context.function_name}",
                )
            except Exception as sns_error:
                logger.error(f"Failed to send error notification: {str(sns_error)}")
        
        raise  # Re-raise to mark CloudFormation deployment as failed