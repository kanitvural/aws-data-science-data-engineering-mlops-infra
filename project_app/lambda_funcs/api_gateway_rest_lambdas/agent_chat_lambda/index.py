# ==================== CHAT LAMBDA ====================

import os
import logging
import boto3
import json
import uuid
from datetime import datetime, timezone
from http import cookies
from botocore.exceptions import ClientError

# === LAMBDA LOGGER SETUP ===
logger = logging.getLogger()
logger.setLevel(logging.INFO)

if not logger.handlers:
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

# === ENVIRONMENT ===
region = os.environ["REGION"]
cloudfront_url = os.environ["CLOUDFRONT_URL"]
client = boto3.client("bedrock-agentcore", region_name=region)
control_client = boto3.client("bedrock-agentcore-control", region_name=region)
cognito_client = boto3.client("cognito-idp", region_name=region)

# Session table for extracting start and end time for feeding to agent dynamodb tool
dynamodb = boto3.resource("dynamodb", region_name=region)
sessions_table = dynamodb.Table(os.environ["SESSIONS_TABLE_NAME"])

# Rate limiting configuration
rate_limit_window = int(os.environ.get("RATE_LIMIT_WINDOW", 60))  
rate_limit_max_requests = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", 20)) 



# === HELPERS ===
def get_memory_id(control_client):
    response = control_client.list_memories(maxResults=50)
    memories = response.get("memories", [])
    if not memories:
        raise ValueError("No memories found in Bedrock AgentCore.")

    for mem in memories:
        if mem.get("status") == "ACTIVE":
            return mem["id"]

    raise ValueError("No ACTIVE memory found.")


def get_agent_runtime_arn(control_client):
    response = control_client.list_agent_runtimes(maxResults=50)
    runtimes = response.get("agentRuntimes", [])
    if not runtimes:
        raise ValueError("No agent runtimes found.")

    for rt in runtimes:
        if rt.get("status") == "READY":
            return rt["agentRuntimeArn"]

    raise ValueError("No READY agent runtime found.")


def get_origin(event):
    return event.get("headers", {}).get("origin", cloudfront_url)


def make_response(status, body, event):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": get_origin(event),
            "Access-Control-Allow-Credentials": "true",
        },
        "body": json.dumps(body),
    }


memory_id = get_memory_id(control_client)
agent_runtime_arn = get_agent_runtime_arn(control_client)


def update_session(session_id, access_token):
    """
    Update existing session and check rate limit.
    
    Session must already exist (created during login).
    Updates last_active, extends TTL, and checks rate limiting.
    
    Args:
        session_id: Session identifier from frontend
        access_token: Cognito access token for validation
    
    Returns:
        tuple: (start_timestamp, end_timestamp)
            - start_timestamp: When session was created (login time)
            - end_timestamp: Current time (prompt time)
    
    Raises:
        Exception: If token expired, session not found, or rate limit exceeded
    """
    try:
        # Validate token
        user_info = cognito_client.get_user(AccessToken=access_token)
        
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # Get existing session
        response = sessions_table.get_item(Key={"session_id": session_id})
        
        if "Item" not in response:
            # Session not found (expired, deleted, or never created)
            logger.warning(f"Session not found: {session_id}")
            raise Exception("Session not found. Please login again.")
        
        item = response["Item"]
        start_timestamp = int(item["start_timestamp"])  # Login time
        request_count = int(item.get("request_count", 0))
        request_window_start = int(item.get("request_window_start", current_time))
        
        # ========== RATE LIMIT CHECK ==========
        if current_time - request_window_start >= rate_limit_window:
            # Window expired - reset
            new_request_count = 1
            new_window_start = current_time
        else:
            # Within window - check limit
            if request_count >= rate_limit_max_requests:
                wait_time = rate_limit_window - (current_time - request_window_start)
                logger.warning(f"Rate limit exceeded: {session_id} ({request_count} requests)")
                raise Exception(f"Rate limit exceeded. Please wait {wait_time} seconds.")
            
            new_request_count = request_count + 1
            new_window_start = request_window_start

        
        # Update session
        sessions_table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET last_active = :now, expiry_time = :exp, request_count = :count, request_window_start = :window",
            ExpressionAttributeValues={
                ":now": current_time,
                ":exp": current_time + 3600,  # Extend TTL by 1 hour
                ":count": new_request_count,
                ":window": new_window_start
            },
        )
        
        logger.info(f"Session updated: {session_id}, duration: {current_time - start_timestamp}s, requests: {new_request_count}/{rate_limit_max_requests}")
        
        return start_timestamp, current_time  # Login time → Now
        
    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning(f"Token expired for session: {session_id}")
        raise Exception("Session expired, please login again")
    
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error(f"DynamoDB error in session update: {error_code} - {str(e)}")
        raise Exception(f"Session update failed: {error_code}")
    
    except Exception as e:
        # Rate limit veya session not found exceptions
        if "Rate limit exceeded" in str(e) or "Session not found" in str(e):
            raise
        logger.error(f"Unexpected error in session update: {str(e)}", exc_info=True)
        raise Exception("Session update failed, please try again")
    

def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    try:

        # === 1. Extract Access Token from Cookie ===
        cookie_header = event.get("headers", {}).get("cookie", "")
        if not cookie_header:
            return make_response(401, {"error": "Unauthorized", "message": "Missing cookies"}, event)

        cookie = cookies.SimpleCookie()
        cookie.load(cookie_header)
        access_token = cookie.get("access_token")
        if not access_token:
            return make_response(401, {"error": "Unauthorized", "message": "Missing access token"}, event)

        # === 2. Validate User ===
        try:
            user_info = cognito_client.get_user(AccessToken=access_token.value)
            user_id = user_info["Username"]
            user_email = next((attr["Value"] for attr in user_info["UserAttributes"] if attr["Name"] == "email"), "")
        except cognito_client.exceptions.NotAuthorizedException:
            return make_response(401, {"error": "Invalid token", "message": "Session expired"}, event)

        logger.info(f"Authenticated user: {user_id} ({user_email})")

        # === 3. Parse Request Body ===
        body = json.loads(event.get("body", "{}"))
        prompt = body.get("prompt")
        session_id = body.get("sessionId")

        if not prompt:
            logger.warning("Missing 'prompt' in request")
            return make_response(400, {"error": "Missing required field", "message": "Prompt is required"}, event)

        if not session_id:
            logger.warning("Missing 'sessionId' in request")
            return make_response(400, {"error": "Missing required field", "message": "SessionId is required"}, event)

        # Create ACTOR_ID with userId from authorizer
        actor_id = f"app/user-{user_id}"
        logger.info(f"Processing chat for actor: {actor_id}, session: {session_id}")

        # === 4. Fetch Conversation History ===
        enhanced_prompt = prompt
        try:
            logger.info("Fetching conversation history from memory")
            history_response = client.list_events(
                memoryId=memory_id,
                actorId=actor_id,
                sessionId=session_id,
                includePayloads=True,
                maxResults=30,
            )

            events = history_response.get("events", [])
            conversation_history = []

            for event_item in reversed(events):
                for payload in event_item.get("payload", []):
                    conv = payload.get("conversational")
                    if conv:
                        role = conv.get("role", "").lower()
                        content = conv.get("content", {})
                        text = content.get("text", "") if isinstance(content, dict) else str(content)
                        if text:
                            conversation_history.append(f"{role}: {text}")

            if conversation_history:
                recent_history = conversation_history[-20:]  # last 20 messages
                context = "\n".join(recent_history)
                enhanced_prompt = f"""Previous conversation:
{context}

Current question: {prompt}

Remember to use the context from previous conversation when answering."""
                logger.info("Enhanced prompt with %d previous messages", len(recent_history))

        except Exception as e:
            logger.warning(f"Could not fetch conversation history: {e}. Proceeding without history.")
            enhanced_prompt = prompt

        # === 5. Save User Message ===
        logger.info("Creating user message event in memory")
        user_event_response = client.create_event(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": "USER", "content": {"text": prompt}}}],
            clientToken=str(uuid.uuid4()),
        )
        logger.info("User event created: %s", user_event_response["event"]["eventId"])

        # === 6. Invoke Agent ===
        
        # Get time interval for multi-agent DynamoDB tool (with rate limiting)
        try:
            start_timestamp, end_timestamp = update_session(session_id, access_token.value)
            logger.info(f"Session window: {start_timestamp} -> {end_timestamp} ({end_timestamp - start_timestamp}s)")
        except Exception as e:
            # Session management failed (token expired, rate limit, or DynamoDB error)
            error_msg = str(e)
            logger.error(f"Session management failed: {error_msg}")
            
            # Check if it's a rate limit error
            if "Rate limit exceeded" in error_msg:
                return make_response(429, {"error": "Too many requests", "message": error_msg}, event)
            else:
                return make_response(401, {"error": "Session error", "message": error_msg}, event)

        payload_str = json.dumps(
            {
                "prompt": enhanced_prompt,
                "session_id": session_id,
                "start_timestamp": start_timestamp, 
                "end_timestamp": end_timestamp, 
            }
        )
        logger.info("Invoking AgentCore runtime with enhanced prompt")

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn, 
            runtimeSessionId=session_id, 
            payload=payload_str, 
            qualifier="DEFAULT"
        )

        response_body = response["response"].read()
        response_data = json.loads(response_body)
        agent_response = response_data.get("result")

        logger.info("Received response from AgentCore: %s", agent_response)

        # === 7. Save Assistant Response ===
        logger.info("Creating assistant message event in memory")
        assistant_event_response = client.create_event(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": "ASSISTANT", "content": {"text": agent_response}}}],
            clientToken=str(uuid.uuid4()),
        )
        logger.info("Assistant event created: %s", assistant_event_response["event"]["eventId"])

        return make_response(200, {"response": agent_response}, event)

    except Exception as e:
        logger.error("Exception occurred: %s", str(e), exc_info=True)
        return make_response(500, {"error": "Internal server error", "message": str(e)}, event)