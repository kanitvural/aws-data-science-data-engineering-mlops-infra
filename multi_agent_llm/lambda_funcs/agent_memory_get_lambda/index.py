import os
import boto3
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_memory_id(control_client):
    response = control_client.list_memories(maxResults=50)
    memories = response.get("memories", [])
    if not memories:
        logger.error("No memories found in Bedrock AgentCore.")
        raise ValueError("No memories found in Bedrock AgentCore.")

    for mem in memories:
        if mem.get("status") == "ACTIVE":
            memory_id = mem["id"]
            logger.info("Found ACTIVE memory: %s", memory_id)
            return memory_id
    raise ValueError("No ACTIVE memory found.")


region = os.environ["REGION"]
ACTOR_ID = "app/user-1234"
client = boto3.client('bedrock-agentcore', region_name=region)
control_client = boto3.client('bedrock-agentcore-control', region_name=region)

memory_id = get_memory_id(control_client)

def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    if event.get("httpMethod") == "OPTIONS":
        logger.info("OPTIONS request - returning CORS headers")
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
        query_params = event.get("queryStringParameters") or {}
        session_id = query_params.get("sessionId")
        
        if not session_id:
            logger.warning("'sessionId' query parameter is missing")
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "'sessionId' query parameter is required."}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                }
            }
        
        logger.info("Fetching events for sessionId: %s", session_id)
        response = client.list_events(
            memoryId=memory_id,
            actorId=ACTOR_ID,
            sessionId=session_id,
            includePayloads=True,
            maxResults=100
        )
        
        events = response.get('events', [])
        logger.info("Retrieved %d events", len(events))
        history = []
        
        for event_item in events:
            payloads = event_item.get('payload', [])
            event_id = event_item.get('eventId', '')
            timestamp = event_item.get('eventTimestamp')
            
            if timestamp and isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            
            for payload in payloads:
                conversational = payload.get('conversational')
                if conversational:
                    role = conversational.get('role', '')
                    content = conversational.get('content', {})
                    text = content.get('text', '') if isinstance(content, dict) else str(content)
                    
                    if text:
                        history.append({
                            "eventId": event_id,
                            "timestamp": timestamp,
                            "role": role,
                            "content": text
                        })
        
        logger.info("Returning %d messages in history", len(history))
        return {
            "statusCode": 200,
            "body": json.dumps({
                "sessionId": session_id,
                "history": history,
                "count": len(history)
            }),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }

    except Exception as e:
        logger.exception("Error processing the request")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Internal server error: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }
