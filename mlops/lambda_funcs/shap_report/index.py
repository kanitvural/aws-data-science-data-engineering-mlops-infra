import os
import json
import boto3
import logging
from datetime import datetime, timezone
from botocore.exceptions import ClientError


# Logging Config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# Configuration
region = os.environ["REGION"]
bucket_name = os.environ["BUCKET_NAME"]
sns_topic_arn = os.environ["SNS_TOPIC_ARN"]
shap_folder_path = 'shap-analysis/'

s3 = boto3.client('s3', region_name=region)
sns = boto3.client('sns', region_name=region)


def generate_presigned_url(bucket_name, object_key, expiration=86400):
    """
    Generate Pre-signed URL (Expires in 24h)
    """
    try:
        response = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        logger.error(f"Failed to generate pre-signed URL: {e}")
        return None


def create_shap_notification_message(timestamp, pdf_presigned_url, file_size_mb, expiry_hours=24):
    """Create SHAP analysis notification message with pre-signed URL"""
    
    message = f"""
🧠 SHAP ANALYSIS COMPLETED ✅
📅 {timestamp}

🎯 EXPLAINABLE AI REPORT READY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Model interpretability analysis finished
🔍 Feature importance rankings generated  
📈 SHAP values calculated successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 REPORT DETAILS
✅ PDF Report Generated: {file_size_mb:.1f} MB
🔒 Secure download link (expires in {expiry_hours} hours)
🎨 Visualizations: Interactive plots included

🔗 SECURE DOWNLOAD LINK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 PDF Report: {pdf_presigned_url}

⏰ LINK EXPIRY: {expiry_hours} hours from now
🔒 SECURE ACCESS: No additional login required

📊 INCLUDED ANALYSES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Feature Importance Rankings
📈 SHAP Value Distributions  
🔍 Individual Prediction Explanations
📊 Summary & Waterfall Plots
🌐 Partial Dependence Analysis
🎨 Force & Decision Plots

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Automated MLOps Pipeline
📧 SHAP Analysis Notification

💡 TIP: Download the report within {expiry_hours} hours. 
   After expiry, a new analysis will generate a fresh link.
"""
    
    return message


def lambda_handler(event, context):
    """S3 trigger handler for SHAP report.pdf uploads"""
    try:
        
        s3_key = event['Records'][0]['s3']['object']['key']
        file_size = event['Records'][0]['s3']['object']['size']
        
        if not s3_key.endswith('report.pdf') or 'shap-analysis' not in s3_key:
            logger.info(f"Not a SHAP report.pdf file: {s3_key}")
            return {'statusCode': 200, 'body': 'Not a SHAP report file'}
        
        logger.info(f"SHAP report.pdf uploaded: {s3_key} ({file_size} bytes)")
        
        try:
            s3.head_object(Bucket=bucket_name, Key=s3_key)
            logger.info("SHAP report.pdf confirmed in S3")
        except Exception as e:
            logger.error(f"Cannot access uploaded file: {str(e)}")
            raise
        
        # Generate Pre-signed URL (Expires in 24h)
        pdf_presigned_url = generate_presigned_url(bucket_name, s3_key, expiration=86400)
        
        if not pdf_presigned_url:
            raise Exception("Cannot create Pre-signed URL")
        
        # Calculate Timestamp and file size
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        file_size_mb = file_size / (1024 * 1024)
        
        
        subject = f"🧠 SHAP Analysis Complete ✅ - {timestamp}"
        message = create_shap_notification_message(
            timestamp, 
            pdf_presigned_url, 
            file_size_mb, 
            expiry_hours=24
        )
        
        # Send SNS Notification
        sns.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject=subject
        )
        
        logger.info("SHAP analysis notification sent successfully via SNS with pre-signed URL")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'SHAP report notification sent with secure link',
                'file_size_mb': round(file_size_mb, 1),
                'timestamp': timestamp,
                'url_expires_in_hours': 24,
                'secure_link_generated': True
            })
        }
    
    except Exception as e:
        error_msg = f"Error processing SHAP report {s3_key if 's3_key' in locals() else 'unknown'}: {str(e)}"
        logger.error(error_msg)
        
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        try:
            sns.publish(
                TopicArn=sns_topic_arn,
                Message=f"""
🚨 SHAP ANALYSIS SYSTEM ERROR

Error: {str(e)}
Time: {timestamp}
File: {s3_key if 's3_key' in locals() else 'Unknown'}

Please check Lambda logs for details.
Expected path: s3://{bucket_name}/shap-analysis/report.pdf

System will retry on next file upload.
""",
                Subject=f"🚨 SHAP System Error - {timestamp}"
            )
        except Exception as sns_error:
            logger.error(f"Failed to send error notification: {sns_error}")
        
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}