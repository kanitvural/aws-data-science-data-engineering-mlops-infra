
## Installation

```bash
cd multi_agent_llm/core
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Store OpenAI Key to the Parameter store

```bash
 aws ssm put-parameter \
  --name "/multi-agent-llm/openai-api-key" \
  --value "your-openai-api-key" \
  --type "String" \
  --overwrite
```

## Create OpenAI Vector Store

```bash
python create_openai_vector_store.py
```


## Localhost Execution

```bash
python flight_multi_agent.py 
```

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "How many flights are ongoing at the moment?"}'

curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is Alaska Airlines average delay?"}'

curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Show me weather information for SEA-SFO route"}'

curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What machine learning model is used in this project?"}'

curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me about Kanıt Vural"}'
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

## Destroy AgentCore App

```bash
agentcore destroy
```
