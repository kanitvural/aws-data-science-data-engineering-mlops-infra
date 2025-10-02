import os
import logging
import boto3
import json
import uuid
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

region = os.environ["REGION"]
MEMORY_ID = "flight_multi_agent_mem-v624VP5DN0"
ACTOR_ID = "app/user-1234"

def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

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
        body = json.loads(event.get("body", "{}"))
        prompt = body.get("prompt")
        session_id = body.get("sessionId")

        if not prompt or not session_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Both 'prompt' and 'sessionId' are required."}),
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                }
            }

        client = boto3.client('bedrock-agentcore', region_name=region)
        
        # 1. FETCH CONVERSATION HISTORY
        enhanced_prompt = prompt
        try:
            logger.info("Fetching conversation history from memory")
            history_response = client.list_events(
                memoryId=MEMORY_ID,
                actorId=ACTOR_ID,
                sessionId=session_id,
                includePayloads=True,
                maxResults=30  
            )
            
            events = history_response.get('events', [])
            
            if events:
                # Sort Hisyory
                conversation_history = []
                for event_item in reversed(events): 
                    for payload in event_item.get('payload', []):
                        conv = payload.get('conversational')
                        if conv:
                            role = conv.get('role', '').lower()
                            content = conv.get('content', {})
                            text = content.get('text', '') if isinstance(content, dict) else str(content)
                            
                            if text:
                                conversation_history.append(f"{role}: {text}")
                
                # Get last 20 messages (10 user + 10 assistant)
                if conversation_history:
                    recent_history = conversation_history[-20:]
                    context = "\n".join(recent_history)
                    
                    # Add context to the prompt
                    enhanced_prompt = f"""Previous conversation:
{context}

Current question: {prompt}

Remember to use the context from previous conversation when answering."""
                    
                    logger.info("Enhanced prompt with %d previous messages", len(recent_history))
            else:
                logger.info("No previous conversation history found")
                
        except Exception as e:
            logger.warning(f"Could not fetch conversation history: {e}. Proceeding without history.")
            enhanced_prompt = prompt
        
        # 2. SAVE USER MESSAGE TO THE MEMORY
        logger.info("Creating user message event in memory")
        user_event_response = client.create_event(
            memoryId=MEMORY_ID,
            actorId=ACTOR_ID,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{
                'conversational': {
                    'role': 'USER',
                    'content': {'text': prompt}
                }
            }],
            clientToken=str(uuid.uuid4())
        )
        logger.info("User event created: %s", user_event_response['event']['eventId'])

        # 3. INVOKE AGENT WITH ENHANCED PROMPT
        payload_str = json.dumps({
            "prompt": enhanced_prompt,
            "session_id": session_id  
        })
        logger.info("Invoking AgentCore runtime with enhanced prompt")

        response = client.invoke_agent_runtime(
            agentRuntimeArn='arn:aws:bedrock-agentcore:eu-central-1:058264126563:runtime/flight_multi_agent-0fbFPQFDfe',
            runtimeSessionId=session_id,
            payload=payload_str,
            qualifier="DEFAULT"
        )

        response_body = response['response'].read()
        response_data = json.loads(response_body)
        agent_response = response_data.get("result")

        logger.info("Received response from AgentCore: %s", agent_response)

        # 4. SAVE ASSISTANT RESPONSE TO THE MEMORY
        logger.info("Creating assistant message event in memory")
        assistant_event_response = client.create_event(
            memoryId=MEMORY_ID,
            actorId=ACTOR_ID,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{
                'conversational': {
                    'role': 'ASSISTANT',
                    'content': {'text': agent_response}
                }
            }],
            clientToken=str(uuid.uuid4())
        )
        logger.info("Assistant event created: %s", assistant_event_response['event']['eventId'])

        return {
            "statusCode": 200,
            "body": json.dumps({"response": agent_response}),
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