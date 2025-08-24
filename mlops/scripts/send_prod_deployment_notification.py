#!/usr/bin/env python3
"""
Production deployment notification script
"""

import boto3
import os
from datetime import datetime
import sys

def get_sns_topic_arn():
    region = os.environ["AWS_DEFAULT_REGION"]
    cf = boto3.client('cloudformation', region_name = region)
    response = cf.describe_stacks(StackName="MLOpsInfraStage-MLOpsNotificationStack")
    for output in response['Stacks'][0]['Outputs']:
        if output['OutputKey'] == 'SNSNotificationTopicArn':
            return output['OutputValue']

def main():
    # Get environment variables
    region = os.environ.get('REGION')
    project_name = os.environ.get('PROJECT_NAME')
    endpoint_name = os.environ.get('ENDPOINT_NAME')
    sns_topic_arn = get_sns_topic_arn()
    
    if not all([region, project_name, endpoint_name, sns_topic_arn]):
        print("❌ Missing environment variables")
        sys.exit(1)
    
    print(f"📧 Sending notification for {project_name}...")
    
    # Initialize clients
    sns_client = boto3.client('sns', region_name=region)
    sagemaker_client = boto3.client('sagemaker', region_name=region)
    autoscaling_client = boto3.client('application-autoscaling', region_name=region)
    
    try:
        # Get endpoint info
        endpoint_response = sagemaker_client.describe_endpoint(EndpointName=endpoint_name)
        status = endpoint_response['EndpointStatus']
        instance_type = endpoint_response['ProductionVariants'][0]['InstanceType']
        instance_count = endpoint_response['ProductionVariants'][0]['DesiredInstanceCount']
        
        # Get autoscaling info
        resource_id = f"endpoint/{endpoint_name}/variant/AllTraffic"
        targets = autoscaling_client.describe_scalable_targets(
            ServiceNamespace='sagemaker',
            ResourceIds=[resource_id]
        )['ScalableTargets']
        
        if targets:
            min_cap = targets[0]['MinCapacity']
            max_cap = targets[0]['MaxCapacity']
            scaling_info = f"{min_cap}-{max_cap} instances"
        else:
            scaling_info = "Not configured"
        
        # Send notification
        subject = f"🚀 Production Endpoint Deployed"
        message = f"""Production endpoint is ready!

Project: {project_name}
Endpoint: {endpoint_name}
Status: {status}
Instance: {instance_type} ({instance_count} current)
AutoScaling: {scaling_info}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}

Your ML model is live."""

        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        
        print("✅ Notification sent!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()