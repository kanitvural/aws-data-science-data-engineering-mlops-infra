import os
import logging
import boto3
import json

# Logging Config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configuration
region = os.environ["REGION"]

def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    # Preflight request (OPTIONS) handling
    if event.get("httpMethod") == "OPTIONS":
        logger.info("Handling preflight OPTIONS request")
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
            "body": ""
        }

    try:
        body = json.loads(event.get("body", "{}"))
        prompt = body.get("prompt")
        session_id = body.get("sessionId")

        logger.info("Parsed body: prompt=%s, sessionId=%s", prompt, session_id)

        if not prompt or not session_id:
            logger.warning("Missing 'prompt' or 'sessionId'")
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Both 'prompt' and 'sessionId' are required."}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                }
            }

        client = boto3.client('bedrock-agentcore', region_name=region)
        payload = json.dumps({"prompt": prompt})

        logger.info("Invoking AgentCore runtime with payload: %s", payload)

        response = client.invoke_agent_runtime(
            agentRuntimeArn='arn:aws:bedrock-agentcore:eu-central-1:058264126563:runtime/multi_agent_restaurant-0D8IWzBTKP',
            runtimeSessionId=session_id,
            payload=payload,
            qualifier="DEFAULT"
        )

        response_body = response['response'].read()
        response_data = json.loads(response_body)

        logger.info("Received response from AgentCore: %s", response_data)

        return {
            "statusCode": 200,
            "body": json.dumps({"response": response_data.get("result")}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except Exception as e:
        logger.error("Exception occurred: %s", str(e), exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": str(e)}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }
