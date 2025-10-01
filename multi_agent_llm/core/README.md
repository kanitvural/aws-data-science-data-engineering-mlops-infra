
## Installation

```bash
cd multi_agent_llm/core
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Localhost Execution

```bash
python flight_multi_agent.py 
```

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, What is the longest delay? And Which airline?"}'
```

The `app.run()` command launches a local HTTP server (by default most frameworks use something like `localhost:8080`).

## Deploy To AWS

AgentCore is actually a containerized system. You write your agent code, and it:

- Wraps it into a Docker container
- Pushes it to ECR (Elastic Container Registry)
- Runs it as a serverless container runtime
- Handles auto-scaling automatically
  
1. Go to Cloudwatch -> Application Signals -> Transaction Search and enable it.
2. Go to bash and type

```bash
agentcore configure \
  --entrypoint flight_multi_agent.py \
  --name flight_multi_agent \
  --execution-role arn:aws:iam::058264126563:role/AgentCoreExecutionRole-multi-agent-llm-058264126563 \
  --ecr 058264126563.dkr.ecr.eu-central-1.amazonaws.com/multi-agent-llm-repository-058264126563 \
  --requirements-file requirements.txt \
  --authorizer-config 'null' \
  --request-header-allowlist '' \
  --region eu-central-1 \
  --non-interactive
```

```bash
export OPENAI_API_KEY="your_openai_api_key"
agentcore launch --env OPENAI_API_KEY=$OPENAI_API_KEY
agentcore invoke '{"prompt": "Hello, What is the longest delay? And Which airline?"}'
```

Go to AWS Console > Amazon Bedrock AgentCore > Agent Runtime > flight_multi_agent and copy the python code. Change region. Save as `agent_test.py`

## Destroy AgentCore App

```bash
agentcore destroy
```
