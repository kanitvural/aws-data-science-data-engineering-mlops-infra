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
rate_limit_window = os.environ["RATE_LIMIT_WINDOW"]
rate_limit_max_requests = os.environ["RATE_LIMIT_MAX_REQUESTS"]



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


def check_rate_limit(session_id, current_time):
    """
    Check if session has exceeded rate limit.
    
    Uses sliding window: tracks requests in last 60 seconds.
    
    Args:
        session_id: Session identifier
        current_time: Current timestamp (Unix)
    
    Raises:
        Exception: If rate limit exceeded (>20 requests/minute)
    
    Returns:
        bool: True if rate limit check passed
    """
    try:
        response = sessions_table.get_item(Key={"session_id": session_id})
        
        if "Item" not in response:
            # New session, no rate limit issue
            return True
        
        item = response["Item"]
        request_count = int(item.get("request_count", 0))
        request_window_start = int(item.get("request_window_start", current_time))
        
        # Check if window has expired (60 seconds passed)
        if current_time - request_window_start >= rate_limit_window:
            # Reset counter - new window starts
            logger.info(f"Rate limit window reset for session: {session_id}")
            return True
        
        # Within window - check count
        if request_count >= rate_limit_max_requests:
            logger.warning(f"Rate limit exceeded for session: {session_id} ({request_count} requests)")
            raise Exception(f"Rate limit exceeded. Please wait {rate_limit_window - (current_time - request_window_start)} seconds.")
        
        logger.info(f"Rate limit check passed: {session_id} ({request_count}/{rate_limit_max_requests})")
        return True
        
    except Exception as e:
        # If it's our rate limit exception, re-raise it
        if "Rate limit exceeded" in str(e):
            raise
        # Otherwise, log and continue (don't block on rate limit check failures)
        logger.error(f"Rate limit check failed: {str(e)}")
        return True


def get_or_create_session(session_id, access_token):
    """
    Manage session lifecycle tied to token expiry with rate limiting.
    
    Args:
        session_id: Unique session identifier from frontend
        access_token: Cognito access token for validation
    
    Returns:
        tuple: (start_timestamp, end_timestamp)
            - start_timestamp: When the session was created
            - end_timestamp: Current time (query time)
    
    Raises:
        Exception: If token is expired, rate limit exceeded, or session management fails
    """
    try:
        # Validate token (raises NotAuthorizedException if expired)
        user_info = cognito_client.get_user(AccessToken=access_token)
        # If there is a valid token, continue; otherwise, it goes to exception block

        current_time = int(datetime.now(timezone.utc).timestamp())
        
        # Check rate limit BEFORE creating/updating session
        check_rate_limit(session_id, current_time)
        
        # Try to get existing session
        response = sessions_table.get_item(Key={"session_id": session_id})

        if "Item" in response:
            # Existing session found
            existing_start = int(response["Item"]["start_timestamp"])
            request_count = int(response["Item"].get("request_count", 0))
            request_window_start = int(response["Item"].get("request_window_start", current_time))
            
            # Check if rate limit window expired
            if current_time - request_window_start >= rate_limit_window:
                # Reset counter - new window
                new_request_count = 1
                new_window_start = current_time
            else:
                # Increment counter within window
                new_request_count = request_count + 1
                new_window_start = request_window_start
            
            # Update session (extend TTL + update rate limit counter)
            sessions_table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET last_active = :now, expiry_time = :exp, request_count = :count, request_window_start = :window",
                ExpressionAttributeValues={
                    ":now": current_time, 
                    ":exp": current_time + 3600,  # Extend by 1 hour
                    ":count": new_request_count,
                    ":window": new_window_start
                },
            )

            logger.info(f"Session extended: {session_id}, duration: {current_time - existing_start}s, requests: {new_request_count}")
            return existing_start, current_time
        
        else:
            # New session - create it
            sessions_table.put_item(
                Item={
                    "session_id": session_id,
                    "start_timestamp": current_time,
                    "last_active": current_time,
                    "expiry_time": current_time + 3600,
                    "request_count": 1,  # First request
                    "request_window_start": current_time
                }
            )
            logger.info(f"New session created: {session_id}")
            return current_time, current_time

    except cognito_client.exceptions.NotAuthorizedException:
        # Token expired → Session invalid
        logger.warning(f"Token expired for session: {session_id}")
        raise Exception("Session expired, please login again")
    
    except ClientError as e:
        # DynamoDB errors (throttling, capacity, etc.)
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error(f"DynamoDB error in session management: {error_code} - {str(e)}")
        raise Exception(f"Session management failed: {error_code}")
    
    except Exception as e:
        # Rate limit or other errors
        if "Rate limit exceeded" in str(e):
            raise  # Re-raise rate limit exceptions
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error in session management: {str(e)}", exc_info=True)
        raise Exception("Session management failed, please try again")


def delete_session(session_id):
    """
    Delete session from DynamoDB (called on logout).
    
    Args:
        session_id: Session identifier to delete
    
    Returns:
        bool: True if deleted successfully
    """
    try:
        sessions_table.delete_item(Key={"session_id": session_id})
        logger.info(f"Session deleted: {session_id}")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete session {session_id}: {str(e)}")
        return False


def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    try:
        # === 0. Check if this is a LOGOUT request ===
        http_method = event.get("httpMethod", "POST")
        path = event.get("path", "")
        
        if http_method == "DELETE" and "/session" in path:
            # Handle logout/session cleanup
            body = json.loads(event.get("body", "{}"))
            session_id = body.get("sessionId")
            
            if not session_id:
                return make_response(400, {"error": "Missing sessionId"}, event)
            
            success = delete_session(session_id)
            if success:
                return make_response(200, {"message": "Session deleted successfully"}, event)
            else:
                return make_response(500, {"error": "Failed to delete session"}, event)
        
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
            start_timestamp, end_timestamp = get_or_create_session(session_id, access_token.value)
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