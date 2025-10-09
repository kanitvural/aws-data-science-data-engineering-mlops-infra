import os
import logging
import boto3
import json
import uuid
from datetime import datetime, timezone
from http import cookies

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
cognito_client = boto3.client("cognito-idp", region_name=region)
client = boto3.client("bedrock-agentcore", region_name=region)
control_client = boto3.client("bedrock-agentcore-control", region_name=region)

# === ALLOWED ORIGINS ===
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    cloudfront_url,
]

# === HELPERS ===
def get_origin(event):
    default_origin = ALLOWED_ORIGINS[0]
    if event and "headers" in event:
        request_origin = event["headers"].get("origin") or event["headers"].get("Origin")
        if request_origin and request_origin in ALLOWED_ORIGINS:
            return request_origin
    return default_origin


def make_response(status, body, event=None):
    origin = get_origin(event)
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type, Cookie, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
    }
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body),
    }

# === MEMORY & RUNTIME ===
def get_memory_id():
    response = control_client.list_memories(maxResults=50)
    for mem in response.get("memories", []):
        if mem.get("status") == "ACTIVE":
            return mem["id"]
    raise ValueError("No ACTIVE memory found in Bedrock AgentCore.")

def get_agent_runtime_arn():
    response = control_client.list_agent_runtimes(maxResults=50)
    for rt in response.get("agentRuntimes", []):
        if rt.get("status") == "READY":
            return rt["agentRuntimeArn"]
    raise ValueError("No READY agent runtime found.")

memory_id = get_memory_id()
agent_runtime_arn = get_agent_runtime_arn()

# === MAIN HANDLER ===
def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    # ✅ Handle CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {}, event)

    try:
        # === 1. Extract Access Token from Cookie ===
        cookie_header = event.get("headers", {}).get("cookie", "")
        if not cookie_header:
            return make_response(401, {"error": "Unauthorized", "message": "Missing cookies"}, event)

        c = cookies.SimpleCookie()
        c.load(cookie_header)
        access_token = c.get("access_token")
        if not access_token:
            return make_response(401, {"error": "Unauthorized", "message": "Missing access token"}, event)

        # === 2. Validate User ===
        try:
            user_info = cognito_client.get_user(AccessToken=access_token.value)
            user_id = user_info["Username"]
            user_email = next(
                (attr["Value"] for attr in user_info["UserAttributes"] if attr["Name"] == "email"),
                ""
            )
        except cognito_client.exceptions.NotAuthorizedException:
            return make_response(401, {"error": "Invalid token", "message": "Session expired"}, event)

        logger.info(f"Authenticated user: {user_id} ({user_email})")


        # === 3. Parse Request Body ===
        body = json.loads(event.get("body", "{}"))
        prompt = body.get("prompt")
        session_id = body.get("sessionId")

        if not prompt or not session_id:
            return make_response(400, {"error": "Missing prompt or sessionId"}, event)

        actor_id = f"app/user-{user_id}"
        logger.info(f"Processing chat for actor: {actor_id}, session: {session_id}")
        

        # === 4. Fetch Conversation History ===
        enhanced_prompt = prompt
        try:
            history_response = client.list_events(
                memoryId=memory_id,
                actorId=actor_id,
                sessionId=session_id,
                includePayloads=True,
                maxResults=30
            )

            events = history_response.get("events", [])
            conversation_history = []
            for event_item in reversed(events):
                for payload in event_item.get("payload", []):
                    conv = payload.get("conversational")
                    if conv:
                        role = conv.get("role", "").lower()
                        text = conv.get("content", {}).get("text", "")
                        if text:
                            conversation_history.append(f"{role}: {text}")

            if conversation_history:
                recent_history = conversation_history[-20:]
                context = "\n".join(recent_history)
                enhanced_prompt = f"""Previous conversation:
{context}

Current question: {prompt}"""
        except Exception as e:
            logger.warning(f"Could not fetch history: {e}")

        # === 5. Save User Message ===
        client.create_event(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": "USER", "content": {"text": prompt}}}],
            clientToken=str(uuid.uuid4()),
        )

        # === 6. Invoke Agent ===
        payload_str = json.dumps({"prompt": enhanced_prompt, "session_id": session_id})
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            runtimeSessionId=session_id,
            payload=payload_str,
            qualifier="DEFAULT"
        )

        response_data = json.loads(response["response"].read())
        agent_response = response_data.get("result", "No response")

        # === 7. Save Assistant Response ===
        client.create_event(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=datetime.now(timezone.utc),
            payload=[{"conversational": {"role": "ASSISTANT", "content": {"text": agent_response}}}],
            clientToken=str(uuid.uuid4()),
        )

        # === 8. Return ===
        return make_response(200, {"response": agent_response}, event)

    except Exception as e:
        logger.exception("Unhandled exception")
        return make_response(500, {"error": "Internal server error", "message": str(e)}, event)
