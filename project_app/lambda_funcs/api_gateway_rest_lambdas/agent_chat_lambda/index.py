# ==================== CHAT LAMBDA ====================

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
CLOUDFRONT_URL = os.environ["CLOUDFRONT_URL"]
client = boto3.client("bedrock-agentcore", region_name=region)
control_client = boto3.client("bedrock-agentcore-control", region_name=region)
cognito_client = boto3.client("cognito-idp", region_name=region)


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
    return event.get("headers", {}).get("origin", CLOUDFRONT_URL)


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

        # ✅ Create ACTOR_ID with userId from authorizer
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
        payload_str = json.dumps({"prompt": enhanced_prompt, "session_id": session_id})
        logger.info("Invoking AgentCore runtime with enhanced prompt")

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn, runtimeSessionId=session_id, payload=payload_str, qualifier="DEFAULT"
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
