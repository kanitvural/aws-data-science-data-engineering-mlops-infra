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


def get_db_credentials(secret_arn):
    """
    Retrieve database credentials from Secrets Manager using boto3
    """
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response['SecretString'])
        return secret.get('username'), secret.get('password')
    except Exception as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise


def send_sns_notification(topic_arn, subject, message):
    """
    Send SNS notification with deployment details
    """
    try:
        response = sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        logger.info(f"SNS notification sent. MessageId: {response['MessageId']}")
        return response
    except Exception as e:
        logger.error(f"Error sending SNS notification: {str(e)}")


def lambda_handler(event, context):
    """
    Lambda function to setup Redshift Spectrum external schema
    """
    
    logger.info(f"Event: {json.dumps(event)}")
    
    request_type = event.get('RequestType', 'Create')
    
    if request_type == 'Delete':
        logger.info("Delete request - no action needed")
        return {
            'PhysicalResourceId': 'spectrum-setup',
            'Data': {'Message': 'Deleted'}
        }
    
    if request_type not in ['Create', 'Update']:
        return {
            'PhysicalResourceId': 'spectrum-setup',
            'Data': {'Message': 'No action taken'}
        }
    
    try:
        # Environment variables
        workgroup_name = os.environ['WORKGROUP_NAME']
        database_name = os.environ['DATABASE_NAME']
        glue_database = os.environ['GLUE_DATABASE']
        iam_role_arn = os.environ['IAM_ROLE_ARN']
        secret_arn = os.environ['SECRET_ARN']
        region = os.environ['REGION']
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        redshift_endpoint = os.environ.get('REDSHIFT_ENDPOINT', 'N/A')
        
        logger.info(f"Setting up Spectrum for workgroup: {workgroup_name}")
        
        # Get credentials from Secrets Manager using boto3
        username, password = get_db_credentials(secret_arn)
        logger.info(f"Retrieved credentials for user: {username}")
        
        # Wait for Redshift to be fully ready
        logger.info("Waiting 30 seconds for Redshift to be fully ready...")
        time.sleep(30)
        
        # Create external schema pointing to Glue Catalog
        create_schema_sql = f"""
        CREATE EXTERNAL SCHEMA IF NOT EXISTS spectrum
        FROM DATA CATALOG
        DATABASE '{glue_database}'
        IAM_ROLE '{iam_role_arn}'
        REGION '{region}';
        """
        
        logger.info(f"Executing SQL: {create_schema_sql}")
        
        # Execute the statement using Redshift Data API
        response = redshift_data.execute_statement(
            WorkgroupName=workgroup_name,
            Database=database_name,
            Sql=create_schema_sql,
            DbUser=username
        )
        
        statement_id = response['Id']
        logger.info(f"Statement ID: {statement_id}")
        
        # Wait for completion
        max_wait = 120
        elapsed = 0
        status = 'SUBMITTED'
        
        while elapsed < max_wait:
            status_response = redshift_data.describe_statement(Id=statement_id)
            status = status_response['Status']
            
            logger.info(f"Statement status: {status} (elapsed: {elapsed}s)")
            
            if status == 'FINISHED':
                logger.info("✅ External schema created successfully!")
                
                # Verify the schema was created
                verify_sql = "SELECT * FROM svv_external_schemas WHERE schemaname = 'spectrum';"
                verify_response = redshift_data.execute_statement(
                    WorkgroupName=workgroup_name,
                    Database=database_name,
                    Sql=verify_sql,
                    DbUser=username
                )
                
                logger.info(f"Verification query ID: {verify_response['Id']}")
                
                # Send notification
                if sns_topic_arn:
                    notification_message = f"""
🎉 Redshift Serverless + Spectrum Deployment Complete!

✅ CONNECTION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoint:  {redshift_endpoint}
  Port:      5439
  Database:  {database_name}
  Username:  {username}
  Password:  {password}
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
  Status:       {status}
  Schema:       spectrum → {glue_database}

🎊 Your data analytics infrastructure is ready!
                    """
                    
                    send_sns_notification(
                        topic_arn=sns_topic_arn,
                        subject="✅ Redshift Serverless Deployment Complete",
                        message=notification_message
                    )
                
                return {
                    'PhysicalResourceId': 'spectrum-setup',
                    'Data': {
                        'Message': 'Spectrum setup completed successfully',
                        'StatementId': statement_id,
                        'Status': 'FINISHED',
                        'SchemaName': 'spectrum',
                        'GlueDatabase': glue_database,
                        'Endpoint': redshift_endpoint,
                        'Database': database_name,
                        'Username': username
                    }
                }
                
            elif status in ['FAILED', 'ABORTED']:
                error = status_response.get('Error', 'Unknown error')
                logger.error(f"❌ Statement failed: {error}")
                
                # If schema already exists, it's still a success
                if 'already exists' in error.lower():
                    logger.info("Schema already exists - treating as success")
                    status = 'FINISHED'
                
                # Send notification
                if sns_topic_arn:
                    status_icon = "✅" if status == 'FINISHED' else "⚠️"
                    
                    notification_message = f"""
{status_icon} Redshift Spectrum Setup: {status}

✅ CONNECTION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoint:  {redshift_endpoint}
  Port:      5439
  Database:  {database_name}
  Username:  {username}
  Password:  {password}
  Workgroup: {workgroup_name}

📊 POWERBI CONNECTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Server:   {redshift_endpoint}
  Port:     5439
  Database: {database_name}
  Username: {username}
  Password: {password}

📝 TEST QUERIES (Run in Query Editor v2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SELECT * FROM svv_external_schemas WHERE schemaname = 'spectrum';

💰 COST INFO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Base Capacity: 8 RPU (~$3.60/hour when active)
  Auto-pause:    5 minutes of inactivity
  Free Tier:     First 300 RPU-hours FREE

✅ DEPLOYMENT STATUS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Statement ID: {statement_id}
  Status:       {status}
  Error:        {error}
  Schema:       spectrum → {glue_database}

🎊 Your data analytics infrastructure is ready!
                    """
                    
                    send_sns_notification(
                        topic_arn=sns_topic_arn,
                        subject=f"{status_icon} Redshift Setup: {status}",
                        message=notification_message
                    )
                
                return {
                    'PhysicalResourceId': 'spectrum-setup',
                    'Data': {
                        'Message': 'Schema already exists' if status == 'FINISHED' else f'Setup issue: {error}',
                        'StatementId': statement_id,
                        'Status': status,
                        'Error': error
                    }
                }
            
            time.sleep(5)
            elapsed += 5
        
        # Timeout
        logger.warning(f"⚠️ Timeout waiting for statement. Last status: {status}")
        
        if sns_topic_arn:
            notification_message = f"""
⚠️ Redshift Spectrum Setup Timeout

✅ CONNECTION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoint:  {redshift_endpoint}
  Port:      5439
  Database:  {database_name}
  Username:  {username}
  Password:  {password}
  Workgroup: {workgroup_name}

📊 POWERBI CONNECTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Server:   {redshift_endpoint}
  Port:     5439
  Database: {database_name}
  Username: {username}
  Password: {password}

📝 TEST QUERIES (Run in Query Editor v2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SELECT * FROM svv_external_schemas WHERE schemaname = 'spectrum';

💰 COST INFO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Base Capacity: 8 RPU (~$3.60/hour when active)
  Auto-pause:    5 minutes of inactivity
  Free Tier:     First 300 RPU-hours FREE

✅ DEPLOYMENT STATUS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Statement ID: {statement_id}
  Status:       {status} (Timeout after {max_wait}s)
  Schema:       spectrum → {glue_database}

🎊 Manual verification may be needed. Deployment continues.
            """
            
            send_sns_notification(
                topic_arn=sns_topic_arn,
                subject="⚠️ Redshift Setup Timeout",
                message=notification_message
            )
        
        return {
            'PhysicalResourceId': 'spectrum-setup',
            'Data': {
                'Message': f'Timeout but deployment continues. Status: {status}',
                'StatementId': statement_id,
                'Status': status
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Exception during setup: {error_msg}")
        
        # Send exception notification
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        if sns_topic_arn:
            notification_message = f"""
❌ Redshift Spectrum Setup Exception

✅ CONNECTION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Endpoint:  {os.environ.get('REDSHIFT_ENDPOINT', 'N/A')}
  Port:      5439
  Database:  {os.environ.get('DATABASE_NAME', 'N/A')}
  Workgroup: {os.environ.get('WORKGROUP_NAME', 'N/A')}

📊 POWERBI CONNECTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Check AWS Console for credentials after manual fix.

📝 TEST QUERIES (Run in Query Editor v2):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SELECT * FROM svv_external_schemas;

💰 COST INFO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Base Capacity: 8 RPU (~$3.60/hour when active)
  Auto-pause:    5 minutes of inactivity
  Free Tier:     First 300 RPU-hours FREE

✅ DEPLOYMENT STATUS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Status: Exception
  Error:  {error_msg}

🎊 Manual intervention required. Check CloudWatch logs.
            """
            
            try:
                send_sns_notification(
                    topic_arn=sns_topic_arn,
                    subject="❌ Redshift Setup Exception",
                    message=notification_message
                )
            except:
                pass
        
        return {
            'PhysicalResourceId': 'spectrum-setup',
            'Data': {
                'Message': f'Exception but deployment continues: {error_msg}',
                'Error': error_msg
            }
        }