import os
import boto3
import json
import logging
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

region = os.environ["REGION"]
client = boto3.client("bedrock-agentcore", region_name=region)
control_client = boto3.client("bedrock-agentcore-control", region_name=region)


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


memory_id = get_memory_id(control_client)


def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    try:
        # ✅ Get userId from Lambda Authorizer context
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        user_id = authorizer.get("userId")
        user_email = authorizer.get("email", "")

        if not user_id:
            logger.error("No userId in authorizer context")
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized", "message": "User authentication failed"})}

        logger.info(f"Authenticated user: {user_id} ({user_email})")

        # Get query parameters
        query_params = event.get("queryStringParameters") or {}
        session_id = query_params.get("sessionId")

        if not session_id:
            logger.warning("'sessionId' query parameter is missing")
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required field", "message": "SessionId query parameter is required"})}

        # ✅ Create ACTOR_ID with userId from authorizer
        actor_id = f"app/user-{user_id}"
        logger.info(f"Fetching history for actor: {actor_id}, session: {session_id}")

        response = client.list_events(
            memoryId=memory_id,
            actorId=actor_id,
            sessionId=session_id,
            includePayloads=True,
            maxResults=100
        )

        events = response.get("events", [])
        logger.info("Retrieved %d events for user %s", len(events), user_id)

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
                        history.append({"eventId": event_id, "timestamp": timestamp, "role": role, "content": text})

        logger.info("Returning %d messages in history", len(history))
        return {
            "statusCode": 200,
            "body": json.dumps({"sessionId": session_id, "userId": user_id, "history": history, "count": len(history)})
        }

    except Exception as e:
        logger.exception("Error processing the request")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error", "message": str(e)})}
