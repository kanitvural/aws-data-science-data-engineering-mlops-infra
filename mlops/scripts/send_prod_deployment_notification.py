#!/usr/bin/env python3
"""
Production deployment notification script
"""

import boto3
import os
import sys
import logging
from datetime import datetime

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_sns_topic_arn():
    region = os.environ["AWS_DEFAULT_REGION"]
    cf = boto3.client('cloudformation', region_name=region)
    response = cf.describe_stacks(StackName="MLOpsInfraStage-MLOpsNotificationStack")
    for output in response['Stacks'][0]['Outputs']:
        if output['OutputKey'] == 'SNSNotificationTopicArn':
            return output['OutputValue']

def main():
    # Get environment variables
    region = os.environ.get("REGION")
    project_name = os.environ.get("PROJECT_NAME")
    endpoint_name = os.environ.get("ENDPOINT_NAME")
    sns_topic_arn = get_sns_topic_arn()

    # Config values from pipeline
    instance_type = os.environ.get("INSTANCE_TYPE")
    instance_count = os.environ.get("INSTANCE_COUNT")
    autoscaling_min = os.environ.get("AUTOSCALING_MIN")
    autoscaling_max = os.environ.get("AUTOSCALING_MAX")

    if not all([region, project_name, endpoint_name, sns_topic_arn, instance_type, instance_count]):
        logging.error("❌ Missing environment variables")
        sys.exit(1)

    logging.info("📧 Sending notification for project: %s", project_name)

    sns_client = boto3.client("sns", region_name=region)

    # Build notification message
    subject = "🚀 Production Endpoint Deployed"
    message = f"""
✨ Your ML model is live and ready for production traffic! ✨

📌 Project: {project_name}
🖥️ Endpoint: {endpoint_name}
⚙️ Instance: {instance_type} x {instance_count}
📈 AutoScaling: {autoscaling_min} - {autoscaling_max} instances
🕒 Deployed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}

✅ Everything looks good. Time to serve predictions!
"""

    try:
        response = sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        logging.info("✅ Notification sent! MessageId: %s", response["MessageId"])
    except Exception as e:
        logging.exception("❌ Failed to send notification: %s", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
