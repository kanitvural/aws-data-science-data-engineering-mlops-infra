
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

## Localhost Test

```bash
python test_flight_agent_local.py           # Run automated tests
python test_flight_agent_local.py interactive  # Interactive chat mode
python test_flight_agent_local.py check       # Check DynamoDB data
```
