### Localhost Execution

```bash
python /multi_agent_bedrock/agent_core/flight_multi_agent.py 
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
agentcore configure -e flight_multi_agent.py 
```

press enter for steps and finally `no` for OAuth authorizer

```
✓ Will auto-create execution role

🏗️  ECR Repository
Press Enter to auto-create ECR repository, or provide ECR Repository URI to use 
existing
ECR Repository URI (or press Enter to auto-create):
✓ Will auto-create ECR repository

🔍 Detected dependency file: requirements.txt
Press Enter to use this file, or type a different path (use Tab for autocomplete):
Path or Press Enter to use detected dependency file:
✓ Using detected file: requirements.txt

🔐 Authorization Configuration
By default, Bedrock AgentCore uses IAM authorization.
Configure OAuth authorizer instead? (yes/no) [no]: no

🔒 Request Header Allowlist
Configure which request headers are allowed to pass through to your agent.
Common headers: Authorization, X-Amzn-Bedrock-AgentCore-Runtime-Custom-*
Configure request header allowlist? (yes/no) [no]:
✓ Using default request header configuration
Configuring BedrockAgentCore agent: data_agent_agentcore
```

```bash
export OPENAI_API_KEY="your_openai_api_key"
agentcore launch --env OPENAI_API_KEY=$OPENAI_API_KEY
agentcore invoke '{"prompt": "Hello, What is the longest delay? And Which airline?"}'
```

Go to AWS Console > Amazon Bedrock AgentCore > Agent Runtime > data_agent_agentcore and copy the python code. Change region. Save as `data_test.py`

## Destroy AgentCore App

```bash
agentcore destroy
```

## Put OpenAI API Key to SSM Parameter Store Manually

```bash
aws ssm put-parameter \
  --name "/multi-agent-llm/openai-api-key" \
  --value "sk-xxxxxxx" \
  --type "String" \
  --overwrite \
  --region eu-central-1
```