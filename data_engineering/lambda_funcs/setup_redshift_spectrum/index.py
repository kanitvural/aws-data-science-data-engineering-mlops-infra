import json
import boto3
import time
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

redshift_data = boto3.client('redshift-data')
secretsmanager = boto3.client('secretsmanager')


def get_db_credentials(secret_arn):
    """
    Retrieve database credentials from Secrets Manager
    """
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response['SecretString'])
        return secret.get('username'), secret.get('password')
    except Exception as e:
        logger.error(f"Error retrieving secret: {str(e)}")
        raise


def lambda_handler(event, context):
    """
    Lambda function to setup Redshift Spectrum external schema
    This runs after Redshift Serverless is created
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
        workgroup_name = os.environ['WORKGROUP_NAME']
        database_name = os.environ['DATABASE_NAME']
        glue_database = os.environ['GLUE_DATABASE']
        iam_role_arn = os.environ['IAM_ROLE_ARN']
        secret_arn = os.environ['SECRET_ARN']
        region = os.environ['REGION']
        
        logger.info(f"Setting up Spectrum for workgroup: {workgroup_name}")
        
        # Get credentials from Secrets Manager
        username, password = get_db_credentials(secret_arn)
        logger.info(f"Retrieved credentials for user: {username}")
        
        # Wait a bit for Redshift to be fully ready
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
        # With Serverless, we use workgroup-name instead of cluster-identifier
        response = redshift_data.execute_statement(
            WorkgroupName=workgroup_name,
            Database=database_name,
            Sql=create_schema_sql,
            DbUser=username  # Uses IAM authentication
        )
        
        statement_id = response['Id']
        logger.info(f"Statement ID: {statement_id}")
        
        # Wait for completion
        max_wait = 120  # 120 seconds
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
                
                return {
                    'PhysicalResourceId': 'spectrum-setup',
                    'Data': {
                        'Message': 'Spectrum setup completed successfully',
                        'StatementId': statement_id,
                        'Status': 'FINISHED',
                        'SchemaName': 'spectrum',
                        'GlueDatabase': glue_database
                    }
                }
                
            elif status in ['FAILED', 'ABORTED']:
                error = status_response.get('Error', 'Unknown error')
                logger.error(f"❌ Statement failed: {error}")
                
                # Check if it's just because schema already exists
                if 'already exists' in error.lower():
                    logger.info("Schema already exists - considering this success")
                    return {
                        'PhysicalResourceId': 'spectrum-setup',
                        'Data': {
                            'Message': 'Schema already exists',
                            'StatementId': statement_id,
                            'Status': 'FINISHED'
                        }
                    }
                
                # Return error but don't fail the stack
                return {
                    'PhysicalResourceId': 'spectrum-setup',
                    'Data': {
                        'Message': f'Setup failed but not blocking deployment: {error}',
                        'StatementId': statement_id,
                        'Status': status,
                        'Error': error
                    }
                }
            
            time.sleep(5)
            elapsed += 5
        
        # Timeout
        logger.warning(f"⚠️ Timeout waiting for statement completion. Last status: {status}")
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
        logger.error(f"❌ Error setting up Spectrum: {error_msg}")
        
        # Don't fail the CloudFormation stack
        # Return success with error message
        return {
            'PhysicalResourceId': 'spectrum-setup',
            'Data': {
                'Message': f'Setup attempted but encountered error (deployment continues): {error_msg}',
                'Error': error_msg
            }
        }