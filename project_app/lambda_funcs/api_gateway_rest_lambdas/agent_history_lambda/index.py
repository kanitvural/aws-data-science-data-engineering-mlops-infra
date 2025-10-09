import os
import boto3
import json
import logging
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


def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    try:
        # ✅ Extract user from cookie
        cookie_header = event.get("headers", {}).get("cookie", "")
        if not cookie_header:
            return make_response(401, {"error": "Unauthorized", "message": "Missing cookies"}, event)

        cookie = cookies.SimpleCookie()
        cookie.load(cookie_header)
        access_token = cookie.get("access_token")
        if not access_token:
            return make_response(401, {"error": "Unauthorized", "message": "Missing access token"}, event)

        try:
            user_info = cognito_client.get_user(AccessToken=access_token.value)
            user_id = user_info["Username"]
            user_email = next((attr["Value"] for attr in user_info["UserAttributes"] if attr["Name"] == "email"), "")
        except cognito_client.exceptions.NotAuthorizedException:
            return make_response(401, {"error": "Invalid token", "message": "Session expired"}, event)

        logger.info(f"Authenticated user: {user_id} ({user_email})")

        # Get query parameters
        query_params = event.get("queryStringParameters") or {}
        session_id = query_params.get("sessionId")

        if not session_id:
            logger.warning("⚠️ Missing required 'sessionId' query parameter.")
            return make_response(
                400, {"error": "Bad Request", "message": "SessionId query parameter is required"}, event
            )

        # ✅ Create ACTOR_ID with userId from authorizer
        actor_id = f"app/user-{user_id}"
        logger.info(f"Fetching history for actor: {actor_id}, session: {session_id}")

        response = client.list_events(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            includePayloads=True,
            maxResults=100,
        )

        events = response.get("events", [])
        logger.info(f"📦 Retrieved {len(events)} events for user {user_id}")

        # Sort events by timestamp ascending (oldest first)
        events.sort(key=lambda e: e["eventTimestamp"])

        history = []
        for event_item in events:
            payloads = event_item.get("payload", [])
            event_id = event_item.get("eventId", "")
            timestamp = event_item.get("eventTimestamp")
            if timestamp and not isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else str(timestamp)

            for payload in payloads:
                conversational = payload.get("conversational")
                if conversational:
                    role = conversational.get("role", "")
                    content = conversational.get("content", {})
                    text = content.get("text", "") if isinstance(content, dict) else str(content)

                    if text:
                        history.append(
                            {
                                "eventId": event_id,
                                "timestamp": timestamp,
                                "role": role,
                                "content": text,
                            }
                        )

        logger.info(f"✅ Returning {len(history)} messages in history.")

        return make_response(
            200,
            {
                "sessionId": session_id,
                "userId": user_id,
                "history": history,
                "count": len(history),
            },
            event
        )

    except Exception as e:
        logger.exception("💥 Error processing the request")
        return make_response(500, {"error": "Internal Server Error", "message": str(e)}, event)