import os
import boto3
import json
import logging
from datetime import datetime
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


# ✅ Allowed origins for CORS
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    cloudfront_url,
]


def get_origin(event):
    """Extract Origin header and return if allowed."""
    headers = event.get("headers", {}) or {}
    origin = headers.get("origin") or headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        return origin
    return ALLOWED_ORIGINS[0]  # fallback (usually CloudFront)


def make_response(status, body, event=None):
    """Create consistent CORS response."""
    origin = get_origin(event or {})
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


def get_memory_id():
    """Return the first ACTIVE memory ID from Bedrock AgentCore."""
    try:
        response = control_client.list_memories(maxResults=50)
        for mem in response.get("memories", []):
            if mem.get("status") == "ACTIVE":
                logger.info(f"✅ Found ACTIVE memory: {mem['id']}")
                return mem["id"]
        raise ValueError("No ACTIVE memory found.")
    except Exception as e:
        logger.error(f"❌ Failed to get memory ID: {e}")
        raise


def lambda_handler(event, context):
    logger.info("📩 Received event: %s", json.dumps(event))

    # ✅ Handle CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {}, event)

    try:
        # ✅ Extract user from cookie
        cookie_header = event.get("headers", {}).get("cookie", "")
        if not cookie_header:
            return make_response(401, {"error": "Unauthorized", "message": "Missing cookies"}, event)

        c = cookies.SimpleCookie()
        c.load(cookie_header)
        access_token = c.get("access_token")
        if not access_token:
            return make_response(401, {"error": "Unauthorized", "message": "Missing access token"}, event)

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


        # ✅ Parse query parameters

        query_params = event.get("queryStringParameters") or {}
        session_id = query_params.get("sessionId")

        if not session_id:
            logger.warning("⚠️ Missing required 'sessionId' query parameter.")
            return make_response(400, {
                "error": "Bad Request",
                "message": "SessionId query parameter is required"
            }, event)

        # ✅ Get Bedrock Memory ID
        memory_id = get_memory_id()

        # ✅ Build actor ID using userId
        actor_id = f"app/user-{user_id}"
        logger.info(f"📜 Fetching history for actor: {actor_id}, session: {session_id}")

        response = client.list_events(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            includePayloads=True,
            maxResults=100
        )

        events = response.get("events", [])
        logger.info(f"📦 Retrieved {len(events)} events for user {user_id}")

        # ✅ Sort and parse events
        events.sort(key=lambda e: e.get("eventTimestamp", ""))

        history = []
        for e in events:
            event_id = e.get("eventId", "")
            timestamp = e.get("eventTimestamp")
            timestamp = str(timestamp) if timestamp else None

            for payload in e.get("payload", []):
                conversational = payload.get("conversational")
                if conversational:
                    role = conversational.get("role", "")
                    content = conversational.get("content", {})
                    text = content.get("text", "") if isinstance(content, dict) else str(content)
                    if text:
                        history.append({
                            "eventId": event_id,
                            "timestamp": timestamp,
                            "role": role,
                            "content": text
                        })

        logger.info(f"✅ Returning {len(history)} messages in history.")

        return make_response(200, {
            "sessionId": session_id,
            "userId": user_id,
            "history": history,
            "count": len(history)
        }, event)

    except Exception as e:
        logger.exception("💥 Error processing the request")
        return make_response(500, {
            "error": "Internal Server Error",
            "message": str(e)
        }, event)
