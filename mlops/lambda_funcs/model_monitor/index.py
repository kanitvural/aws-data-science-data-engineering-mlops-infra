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


s3 = boto3.client('s3', region_name=region)
sns = boto3.client('sns', region_name=region)

def format_message(violations, timestamp):
    """Create a modern, clean formatted message with emojis"""
    
    # Separate violation types
    data_quality_violations = [v for v in violations if 'data_type_check' in v['constraint_check_type'] or 'null' in v['constraint_check_type']]
    drift_violations = [v for v in violations if 'baseline_drift_check' in v['constraint_check_type']]
    
    # Header with summary stats
    message = f"""
🤖 ML MODEL MONITORING
📅 {timestamp}

📊 QUICK STATS
━━━━━━━━━━━━━━━━━━━━━━━━
🔢 Total Issues: {len(violations)}
🔍 Data Quality: {len(data_quality_violations)}
📈 Drift Issues: {len(drift_violations)}
━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    # Data Quality Section
    message += "\n🔍 DATA QUALITY ISSUES\n"
    if data_quality_violations:
        for i, violation in enumerate(data_quality_violations, 1):
            message += f"""
❌ Issue #{i}
   🏷️  Feature: {violation.get('feature_name', 'Unknown')}
   ⚙️  Check: {violation.get('constraint_check_type', 'Unknown')}
   📝 Details: {violation.get('description', 'No description')}
   ────────────────────────
"""
    else:
        message += "✅ All good! No data quality issues detected.\n"
    
    # Drift Analysis Section
    message += "\n📈 DRIFT ANALYSIS\n"
    if drift_violations:
        for i, violation in enumerate(drift_violations, 1):
            message += f"""
⚠️  Drift #{i}
   🏷️  Feature: {violation.get('feature_name', 'Unknown')}
   ⚙️  Check: {violation.get('constraint_check_type', 'Unknown')}
   📝 Details: {violation.get('description', 'No description')}
   ────────────────────────
"""
    else:
        message += "✅ All stable! No significant drift detected.\n"
    
    # Footer
    message += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n🔔 Automated MLOps Alert\n📊 Check CloudWatch/S3 for detailed logs"
    
    return message

def lambda_handler(event, context):
    """Main Lambda handler with enhanced email formatting"""
    try:
        # Extract S3 information from event
        s3_key = event['Records'][0]['s3']['object']['key']
        
        if 'constraint_violations.json' not in s3_key:
            logger.info(f"Not a constraint violations file: {s3_key}")
            return {'statusCode': 200, 'body': 'Not a violation file'}
        
        logger.info(f"Processing ML monitoring file: {s3_key}")
        
        # Read the violations file from S3
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        violations = data.get('violations', [])
        
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Determine message subject and priority
        if not violations:
            subject = f"✅ ML Monitoring: All Clear - {timestamp}"
            message = f"""
🤖 ML MODEL STATUS: ALL CLEAR ✅
📅 {timestamp}

🎉 GREAT NEWS!
━━━━━━━━━━━━━━━━━━━━━━━━
✅ All data quality checks passed
✅ No significant drift detected
✅ Models performing optimally

🚀 Your ML pipeline is running smoothly!
"""
        else:
            # Determine severity
            severity_icon = "🔴" if len(violations) > 5 else "🟡" if len(violations) > 2 else "🔵"
            severity_text = "CRITICAL" if len(violations) > 5 else "WARNING" if len(violations) > 2 else "INFO"
            subject = f"{severity_icon} ML Alert: {severity_text} - {len(violations)} Issues - {timestamp}"
            
            # Create formatted message
            message = format_message(violations, timestamp)
        
        # Send enhanced SNS notification
        sns.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject=subject
        )
        
        logger.info(f"Enhanced ML monitoring notification sent successfully. Violations: {len(violations)}")
        return {
            'statusCode': 200, 
            'body': json.dumps({
                'message': 'Enhanced notification sent',
                'violations_count': len(violations),
                'timestamp': timestamp
            })
        }
    
    except Exception as e:
        error_msg = f"Error processing ML monitoring file {s3_key if 's3_key' in locals() else 'unknown'}: {str(e)}"
        logger.error(error_msg)
        
        # Send error notification
        try:
            sns.publish(
                TopicArn=sns_topic_arn,
                Message=f"🚨 ML Monitoring System Error\n\nError: {str(e)}\nTime: {timestamp}\n\nPlease check the Lambda logs for more details.",
                Subject=f"🚨 ML Monitoring System Error - {timestamp}"
            )
        except:
            logger.error("Failed to send error notification")
        
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}