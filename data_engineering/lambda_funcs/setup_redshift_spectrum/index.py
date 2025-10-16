import json
import boto3
import time
import os
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
workgroup_name = os.environ["WORKGROUP_NAME"]
glue_database = os.environ["GLUE_DATABASE"]
iam_role_arn = os.environ["IAM_ROLE_ARN"]
secret_arn = os.environ["SECRET_ARN"]
region = os.environ["REGION"]
sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
redshift_endpoint = os.environ.get("REDSHIFT_ENDPOINT", "N/A")
database_name = os.environ["DATABASE_NAME"]

# Initialize clients with explicit region
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
    if not topic_arn:
        logger.warning("SNS Topic ARN not provided, skipping notification")
        return None
    
    try:
        response = sns.publish(TopicArn=topic_arn, Subject=subject, Message=message)
        logger.info(f"✅ SNS sent successfully. MessageId: {response['MessageId']}")
        return response
    except Exception as e:
        logger.error(f"❌ Failed to send SNS: {str(e)}", exc_info=True)
        return None


def execute_sql_with_wait(sql, description):
    """
    Execute SQL and wait for completion with detailed logging
    """
    logger.info(f"🔄 Executing: {description}")
    logger.info(f"📊 Parameters:")
    logger.info(f"  WorkgroupName: {workgroup_name}")
    logger.info(f"  Database: {database_name}")
    logger.info(f"  SecretArn: {secret_arn}")
    logger.info(f"  SQL length: {len(sql)} chars")
    
    try:
        
        response = redshift_data.execute_statement(
            WorkgroupName=workgroup_name,
            Database=database_name,
            SecretArn=secret_arn,
            Sql=sql,
        )
        
        statement_id = response["Id"]
        logger.info(f"✅ Statement submitted. ID: {statement_id}")
        
        # Wait for completion with detailed status logging
        max_wait = 180  # 3 minutes
        elapsed = 0
        
        while elapsed < max_wait:
            status_response = redshift_data.describe_statement(Id=statement_id)
            status = status_response["Status"]
            
            logger.info(f"⏱️  Status after {elapsed}s: {status}")
            
            if status == "FINISHED":
                result_rows = status_response.get("ResultRows", 0)
                logger.info(f"✅ {description} - SUCCESS (Rows: {result_rows})")
                return statement_id, status, None
            elif status in ["FAILED", "ABORTED"]:
                error = status_response.get("Error", "Unknown error")
                query_string = status_response.get("QueryString", "N/A")
                logger.error(f"❌ {description} - FAILED")
                logger.error(f"  Error: {error}")
                logger.error(f"  Query: {query_string[:200]}")
                return statement_id, status, error
            
            time.sleep(5)
            elapsed += 5
        
        logger.warning(f"⚠️  {description} - TIMEOUT after {max_wait}s")
        return statement_id, "TIMEOUT", "Statement execution timeout"
        
    except Exception as e:
        logger.error(f"❌ Exception during SQL execution: {str(e)}", exc_info=True)
        raise


def lambda_handler(event, context):
    logger.info("=" * 80)
    logger.info("🚀 Redshift Spectrum Setup Lambda Started")
    logger.info("=" * 80)
    logger.info(f"Event: {json.dumps(event, indent=2)}")
    logger.info(f"Environment:")
    logger.info(f"  Region: {region}")
    logger.info(f"  Workgroup: {workgroup_name}")
    logger.info(f"  Database: {database_name}")
    logger.info(f"  Glue DB: {glue_database}")
    logger.info(f"  Endpoint: {redshift_endpoint}")
    
    request_type = event.get("RequestType", "Create")
    logger.info(f"📝 Request Type: {request_type}")
    
    if request_type == "Delete":
        logger.info("🗑️  Delete request - no action needed")
        return {"PhysicalResourceId": "spectrum-setup", "Data": {"Message": "Deleted"}}
    
    try:
        # Get credentials for notification
        logger.info("🔐 Retrieving credentials from Secrets Manager...")
        username, password = get_db_credentials(secret_arn)
        logger.info(f"✅ Retrieved credentials for user: {username}")
        
        # Wait for Redshift to be fully ready
        wait_time = 90
        logger.info(f"⏳ Waiting {wait_time} seconds for Redshift Serverless to be ready...")
        time.sleep(wait_time)
        
        # Create external schema
        create_schema_sql = f"""
CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
FROM DATA CATALOG
DATABASE '{glue_database}'
IAM_ROLE '{iam_role_arn}'
REGION '{region}';
        """.strip()
        
        logger.info("📊 SQL to execute:")
        logger.info(create_schema_sql)
        
        statement_id, status, error = execute_sql_with_wait(
            create_schema_sql, 
            "CREATE EXTERNAL SCHEMA spectrum"
        )
        
        # Prepare result
        result = {
            "PhysicalResourceId": "spectrum-setup",
            "Data": {
                "Message": "Spectrum setup completed",
                "StatementId": statement_id,
                "Status": status,
                "GlueDatabase": glue_database,
                "Endpoint": redshift_endpoint,
                "Username": username,
            },
        }
        
        if error:
            result["Data"]["Error"] = error
        
        # Prepare SNS notification
        if status == "FINISHED":
            notification_subject = "✅ Redshift Spectrum Deployment Complete"
            notification_status = "SUCCESS ✅"
        else:
            notification_subject = "⚠️ Redshift Spectrum Deployment Issue"
            notification_status = f"FAILED ❌\nError: {error}"
        
        message = f"""
🎉 Redshift Serverless + Spectrum Deployment Status

✅ CONNECTION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoint:  {redshift_endpoint}
  Port:      5439
  Workgroup: {workgroup_name}
  Database:  {database_name}

📊 POWERBI CONNECTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Server:   {redshift_endpoint}
  Port:     5439
  Database: {database_name}
  Username: {username}
  Password: {password}
  
  ⚠️  Use DirectQuery mode, NOT Import!

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
  Auto-pause:    After 5 minutes of inactivity
  Free Tier:     First 300 RPU-hours FREE each month

✅ DEPLOYMENT STATUS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Statement ID: {statement_id}
  Status:       {notification_status}
  Schema:       spectrum → {glue_database}

🎊 Your data analytics infrastructure is ready!

📚 Resources:
  - CloudWatch Logs: /aws/lambda/{context.function_name}
  - Query Editor v2: https://console.aws.amazon.com/sqlworkbench/home
        """
        
        # Send SNS notification
        send_sns_notification(sns_topic_arn, notification_subject, message)
        
        logger.info("=" * 80)
        logger.info(f"✅ Lambda execution completed: {status}")
        logger.info("=" * 80)
        
        return result
    
    except Exception as e:
        error_msg = str(e)
        logger.error("=" * 80)
        logger.error(f"❌ EXCEPTION: {error_msg}")
        logger.error("=" * 80)
        logger.error("Full traceback:", exc_info=True)
        
        # Send error notification
        if sns_topic_arn:
            error_notification = f"""
❌ Redshift Spectrum Setup Failed

Error: {error_msg}

Check CloudWatch Logs for details:
/aws/lambda/{context.function_name}

Request ID: {context.request_id}
            """
            send_sns_notification(
                sns_topic_arn,
                "❌ Redshift Spectrum Setup Exception",
                error_notification,
            )
        
        # Re-raise to mark CloudFormation deployment as failed
        raise