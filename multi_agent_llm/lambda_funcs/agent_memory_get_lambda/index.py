import boto3
import json
from datetime import datetime

MEMORY_ID = "flight_multi_agent_mem-v624VP5DN0"
ACTOR_ID = "app/user-1234"

def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
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
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "'sessionId' query parameter is required."}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                }
            }

        # bedrock-agentcore client
        client = boto3.client('bedrock-agentcore', region_name='eu-central-1')
        
        # ListEvents API
        response = client.list_events(
            memoryId=MEMORY_ID,
            actorId=ACTOR_ID,
            sessionId=session_id,
            includePayloads=True,
            maxResults=100
        )
        
        events = response.get('events', [])
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
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Internal server error: {str(e)}"}),
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        }