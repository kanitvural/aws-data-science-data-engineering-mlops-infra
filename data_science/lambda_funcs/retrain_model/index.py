import os
import json
import boto3
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

region = os.environ["REGION"]
pipeline_name = os.environ["PIPELINE_NAME"]
sns_topic_arn = os.environ["SNS_TOPIC_ARN"]


def lambda_handler(event, context):
    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            logger.info(f"S3 Event: {bucket}/{key}")
            
            if key == "retrain_data/new_predictions.csv":
                logger.info("Retrain data detected! Sending notification and triggering pipeline...")
                
                # 1. Send notification email
                send_notification_email(bucket, key)
                
                # 2. Trigger pipeline
                trigger_pipeline()
                
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Notification sent and pipeline triggered successfully',
                        'bucket': bucket,
                        'key': key
                    })
                }
            else:
                logger.info(f"Ignoring file: {key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('No action needed')
        }
        
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

def send_notification_email(bucket, key):
    """Send notification email to data science team"""
    try:
        sns = boto3.client('sns', region_name=region)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        subject = "MLOps Alert: Model Retraining Pipeline Triggered"
        
        message = f"""
Dear Data Science Team,

Our MLOps monitoring system has detected data drift and quality issues in the production model.

DETECTED ISSUES:
- Data drift in production model
- Data quality degradation in incoming predictions
- Model performance below acceptable thresholds

AUTOMATIC ACTIONS TAKEN:
- New training data prepared from recent predictions
- Location: s3://{bucket}/{key}
- Timestamp: {timestamp}
- Retraining pipeline automatically triggered

PIPELINE DETAILS:
- Pipeline: {pipeline_name}
- Status: Starting retraining process
- Expected completion: 30-45 minutes

The system will automatically:
1. Combine Athena sample data with new prediction data
2. Shuffle and prepare the merged dataset for training
3. Feed the combined data to the data science training pipeline

You can monitor the progress in the AWS CodePipeline console.

This is an automated response to maintain model performance and data quality.

Best regards,
MLOps Automation System
        """
        
        response = sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info(f"Notification email sent! MessageId: {response['MessageId']}")
        
    except Exception as e:
        logger.error(f"Error sending notification email: {str(e)}")
        raise e

def trigger_pipeline():
    """Trigger the data science pipeline"""
    try:
        codepipeline = boto3.client('codepipeline', region_name=region)
        
        response = codepipeline.start_pipeline_execution(
            name=pipeline_name
        )
        
        execution_id = response['pipelineExecutionId']
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        logger.info(f"Pipeline triggered successfully!")
        logger.info(f"   - Pipeline: {pipeline_name}")
        logger.info(f"   - Execution ID: {execution_id}")
        logger.info(f"   - Timestamp: {timestamp}")
        
    except Exception as e:
        logger.error(f"Error triggering pipeline: {str(e)}")
        raise e