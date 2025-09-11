import os
import json
import boto3
import logging
from datetime import datetime, timezone


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
s3_base_url = f"https://{bucket_name}.s3.eu-central-1.amazonaws.com"

s3 = boto3.client('s3', region_name=region)
sns = boto3.client('sns', region_name=region)


def create_shap_notification_message(timestamp, pdf_url, folder_url, file_size_mb):
    """Create SHAP analysis notification message"""
    
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
📁 Analysis Folder: Complete dataset available
🎨 Visualizations: Interactive plots included

🔗 DOWNLOAD LINKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 PDF Report: {pdf_url}
📂 Full Analysis: {folder_url}

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
"""
    
    return message

def lambda_handler(event, context):
    """S3 trigger handler for SHAP report.pdf uploads"""
    try:
        # S3 Event'den dosya bilgisi al
        s3_key = event['Records'][0]['s3']['object']['key']
        file_size = event['Records'][0]['s3']['object']['size']
        
        # Sadece report.pdf dosyası için çalış
        if not s3_key.endswith('report.pdf') or 'shap-analysis' not in s3_key:
            logger.info(f"Not a SHAP report.pdf file: {s3_key}")
            return {'statusCode': 200, 'body': 'Not a SHAP report file'}
        
        logger.info(f"SHAP report.pdf uploaded: {s3_key} ({file_size} bytes)")
        
        # URLs oluştur
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        pdf_url = f"{s3_base_url}/{s3_key}"
        folder_url = f"{s3_base_url}/{shap_folder_path}"
        file_size_mb = file_size / (1024 * 1024)
        
        # PDF'in gerçekten var olduğunu kontrol et
        try:
            s3.head_object(Bucket=bucket_name, Key=s3_key)
            logger.info("SHAP report.pdf confirmed in S3")
        except Exception as e:
            logger.error(f"Cannot access uploaded file: {str(e)}")
            raise
        
        # Bildirim mesajını oluştur
        subject = f"🧠 SHAP Analysis Complete ✅ - {timestamp}"
        message = create_shap_notification_message(timestamp, pdf_url, folder_url, file_size_mb)
        
        # SNS ile bildirim gönder
        sns.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject=subject
        )
        
        logger.info("SHAP analysis notification sent successfully via SNS")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'SHAP report notification sent',
                'pdf_url': pdf_url,
                'folder_url': folder_url,
                'file_size_mb': round(file_size_mb, 1),
                'timestamp': timestamp
            })
        }
    
    except Exception as e:
        error_msg = f"Error processing SHAP report {s3_key if 's3_key' in locals() else 'unknown'}: {str(e)}"
        logger.error(error_msg)
        
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
""",
                Subject=f"🚨 SHAP System Error - {timestamp}"
            )
        except:
            logger.error("Failed to send error notification")
        
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}