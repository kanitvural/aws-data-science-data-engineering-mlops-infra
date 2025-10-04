#!/usr/bin/env python3
"""
Multi agent Production deployment notification script
"""

import boto3
import os
import sys
import logging
from datetime import datetime

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_sns_topic_arn(cf_client):
    """Get SNS Topic ARN from CloudFormation stack"""
    try:

        stack_name = "MultiAgentLLMInfraStage-MultiAgentNotificationStack"
        
        response = cf_client.describe_stacks(StackName=stack_name)

        for output in response["Stacks"][0]["Outputs"]:
            if output["OutputKey"] == "MultiAgentSNSNotificationTopicArn":
                return output["OutputValue"]

        logger.error("SNS Topic ARN not found in stack outputs")
        return None
    except Exception as e:
        logger.error(f"Failed to get SNS Topic ARN: {e}")
        return None


def get_api_gateway_url(apigw_client, project_name, region):
    """Get API Gateway URL for the agent"""
    try:
        response = apigw_client.get_rest_apis()
        for api in response.get("items", []):
            if f"{project_name}-api" in api["name"].lower():
                api_id = api["id"]
                return f"https://{api_id}.execute-api.{region}.amazonaws.com/prod"

        logger.warning("API Gateway URL not found, will use placeholder")
        return "Check AWS Console for API URL"
    except Exception as e:
        logger.warning(f"Failed to get API Gateway URL: {e}")
        return "Check AWS Console for API URL"


def get_memory_id(control_client):
    """Get active memory ID from Bedrock AgentCore"""
    try:
        response = control_client.list_memories(maxResults=50)
        memories = response.get("memories", [])

        for mem in memories:
            if mem.get("status") == "ACTIVE":
                return mem["id"]

        logger.warning("No ACTIVE memory found")
        return "N/A"
    except Exception as e:
        logger.warning(f"Failed to get memory ID: {e}")
        return "N/A"


def get_agent_runtime_arn(control_client):
    """Get ready agent runtime ARN from Bedrock AgentCore"""
    try:
        response = control_client.list_agent_runtimes(maxResults=50)
        runtimes = response.get("agentRuntimes", [])

        for rt in runtimes:
            if rt.get("status") == "READY":
                return rt["agentRuntimeArn"]

        logger.warning("No READY agent runtime found")
        return "N/A"
    except Exception as e:
        logger.warning(f"Failed to get runtime ARN: {e}")
        return "N/A"


def main():
    # Get environment variables
    region = os.environ["REGION"]
    ecr_repository = os.environ["ECR_REPOSITORY"]
    execution_role_arn = os.environ["AGENTCORE_EXECUTION_ROLE_ARN"]
    project_name = os.environ["PROJECT_NAME"]

    if not region:
        logger.error("REGION environment variable is required")
        sys.exit(1)

    logger.info("Preparing deployment notification...")

    # Initialize AWS clients
    sns_client = boto3.client("sns", region_name=region)
    cf_client = boto3.client("cloudformation", region_name=region)
    apigw_client = boto3.client("apigateway", region_name=region)
    control_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Gather deployment information
    logger.info("Gathering deployment information...")

    sns_topic_arn = get_sns_topic_arn(cf_client)
    if not sns_topic_arn:
        logger.error("Could not retrieve SNS Topic ARN")
        sys.exit(1)

    api_url = get_api_gateway_url(apigw_client, project_name, region)
    memory_id = get_memory_id(control_client)
    agent_runtime_arn = get_agent_runtime_arn(control_client)

    deployment_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build notification message
    subject = "Flight Multi-Agent Deployed Successfully"

    message = f"""
    FLIGHT MULTI-AGENT DEPLOYMENT SUCCESSFUL

    Status: DEPLOYED
    Time: {deployment_time}
    Region: {region}

    API ENDPOINTS:

    POST {api_url}/chat
    Send chat messages to agent
    Body: {{"prompt": "...", "sessionId": "..."}}

    GET {api_url}/history?sessionId=YOUR_SESSION_ID
    Get conversation history

    RESOURCE DETAILS:
    Memory ID: {memory_id}
    Runtime ARN: {agent_runtime_arn}
    ECR Repository: {ecr_repository}
    Execution Role: {execution_role_arn}

    POSTMAN EXAMPLES:

    1. Send a chat message (POST):
    URL: {api_url}/chat
    Method: POST
    Headers: Content-Type: application/json
    Body (raw JSON):
    {{
        "prompt": "How many flights are currently in the system?",
        "sessionId": "dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmtvural"
    }}

    2. Get conversation history (GET):
    URL: {api_url}/history?sessionId=dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmtvural
    Method: GET

    MONITORING:
    CloudWatch Logs: /aws/lambda/flight_multi_agent*
    Bedrock Console: Monitor memory events and runtime status

    Your multi-agent flight booking system is now live!
    """

    # Send notification
    try:
        logger.info("Sending SNS notification...")
        response = sns_client.publish(TopicArn=sns_topic_arn, Subject=subject, Message=message)
        logger.info(f"Notification sent successfully! MessageId: {response['MessageId']}")
        logger.info(f"Email sent to subscribers of topic: {sns_topic_arn}")

    except Exception as e:
        logger.exception(f"Failed to send notification: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
