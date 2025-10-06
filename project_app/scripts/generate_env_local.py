# project_app/scripts/generate_env.py
import os
import sys
import boto3
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


region = os.getenv("REGION", "eu-central-1")
output_file = os.path.join(os.getcwd(), ".env.local")

apigw_client = boto3.client("apigateway", region_name=region)

def get_api_gateway_url(api_name_substring):
    try:
        response = apigw_client.get_rest_apis()
        for api in response.get("items", []):
            if api_name_substring.lower() in api["name"].lower():
                api_id = api["id"]
                return f"https://{api_id}.execute-api.{region}.amazonaws.com/prod"
        logger.warning(f"{api_name_substring} API not found")
        return "CHECK_API_URL"
    except Exception as e:
        logger.warning(f"Failed to get API Gateway URL: {e}")
        return "CHECK_API_URL"

def get_websocket_url(api_name_substring):
    try:
        response = apigw_client.get_rest_apis()
        for api in response.get("items", []):
            if api_name_substring.lower() in api["name"].lower():
                api_id = api["id"]
                return f"wss://{api_id}.execute-api.{region}.amazonaws.com/prod"
        logger.warning(f"{api_name_substring} WebSocket API not found")
        return "CHECK_WS_URL"
    except Exception as e:
        logger.warning(f"Failed to get WebSocket URL: {e}")
        return "CHECK_WS_URL"

if __name__ == "__main__":
    env_lines = [
        f"NEXT_PUBLIC_WEBSOCKET_URL={get_websocket_url('FlightAIWebSocketAPI')}",
        f"NEXT_PUBLIC_APIGATEWAY_CHATBOT_URL={get_api_gateway_url('FlightAIMultiAgentLLMApi')}",
        f"NEXT_PUBLIC_API_GATEWAY_AUTH_URL={get_api_gateway_url('FlightAIAuthAPI')}",
    ]

    with open(output_file, "w") as f:
        f.write("\n".join(env_lines))

    logger.info(f".env.local file generated at {region}")
