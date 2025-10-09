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
client = boto3.client("bedrock-agentcore", region_name=region)
control_client = boto3.client("bedrock-agentcore-control", region_name=region)


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


memory_id = get_memory_id(control_client)
agent_runtime_arn = get_agent_runtime_arn(control_client)


def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    try:
        # ✅ Get userId from Lambda Authorizer context
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        user_id = authorizer.get("userId")
        user_email = authorizer.get("email", "")

        if not user_id:
            logger.error("No userId in authorizer context")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized", "message": "User authentication failed"})
            }

        logger.info(f"Authenticated user: {user_id} ({user_email})")

        # Get request body
        body = json.loads(event.get("body", "{}"))
        prompt = body.get("prompt")
        session_id = body.get("sessionId")

        if not prompt:
            logger.warning("Missing 'prompt' in request")
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required field", "message": "Prompt is required"})}

        if not session_id:
            logger.warning("Missing 'sessionId' in request")
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required field", "message": "SessionId is required"})}

        # ✅ Create ACTOR_ID with userId from authorizer
        actor_id = f"app/user-{user_id}"
        logger.info(f"Processing chat for actor: {actor_id}, session: {session_id}")

        # 1. FETCH CONVERSATION HISTORY
        enhanced_prompt = prompt
        try:
            logger.info("Fetching conversation history from memory")
            history_response = client.list_events(
                memoryId=memory_id, actorId=actor_id, sessionId=session_id, includePayloads=True, maxResults=30
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

        # 2. SAVE USER MESSAGE TO THE MEMORY
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

        # 3. INVOKE AGENT WITH ENHANCED PROMPT
        payload_str = json.dumps({"prompt": enhanced_prompt, "session_id": session_id})
        logger.info("Invoking AgentCore runtime with enhanced prompt")

        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn, runtimeSessionId=session_id, payload=payload_str, qualifier="DEFAULT"
        )

        response_body = response["response"].read()
        response_data = json.loads(response_body)
        agent_response = response_data.get("result")

        logger.info("Received response from AgentCore: %s", agent_response)

        # 4. SAVE ASSISTANT RESPONSE TO THE MEMORY
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

        return {"statusCode": 200, "body": json.dumps({"response": agent_response})}

    except Exception as e:
        logger.error("Exception occurred: %s", str(e), exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error", "message": str(e)})}
