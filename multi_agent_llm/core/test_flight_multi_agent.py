"""
Local testing script for flight_multi_agent.py

This script simulates the Lambda /chat handler behavior locally.
It allows you to test the agent without deploying to AWS.

Requirements:
1. AWS credentials configured (for DynamoDB access)
2. OpenAI API key in .env file
3. DynamoDB tables must exist (raw-flights with GSI, agent-sessions)
4. Vector store must be created in OpenAI

Usage:
    python test_flight_agent_local.py
"""

import asyncio
import json
import sys
from datetime import datetime, timezone

# Test payload - simulates what /chat Lambda sends
TEST_PAYLOADS = [
    {
        "name": "Flight Count Query",
        "payload": {
            "prompt": "How many flights are there right now?",
            "session_id": "test-session-001",
            "start_timestamp": int(datetime.now(timezone.utc).timestamp()) - 600,  # 10 minutes ago
            "end_timestamp": int(datetime.now(timezone.utc).timestamp())
        }
    },
    {
        "name": "Airline Delay Query",
        "payload": {
            "prompt": "What is Alaska Airlines' average delay?",
            "session_id": "test-session-001",
            "start_timestamp": int(datetime.now(timezone.utc).timestamp()) - 600,
            "end_timestamp": int(datetime.now(timezone.utc).timestamp())
        }
    },
    {
        "name": "Route Weather Query",
        "payload": {
            "prompt": "What's the weather like on the SEA-SFO route?",
            "session_id": "test-session-001",
            "start_timestamp": int(datetime.now(timezone.utc).timestamp()) - 600,
            "end_timestamp": int(datetime.now(timezone.utc).timestamp())
        }
    },
    {
        "name": "Project Info Query",
        "payload": {
            "prompt": "What machine learning model does this project use?",
            "session_id": "test-session-002",
            "start_timestamp": int(datetime.now(timezone.utc).timestamp()) - 300,
            "end_timestamp": int(datetime.now(timezone.utc).timestamp())
        }
    }
]


async def test_agent():
    """Test the agent with various queries"""
    
    print("=" * 80)
    print("🧪 FLIGHT MULTI-AGENT LOCAL TESTING")
    print("=" * 80)
    print()
    
    # Import agent module
    try:
        import sys, os
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from flight_multi_agent import invoke
        print("✅ Successfully imported flight_multi_agent module")
    except ImportError as e:
        print(f"❌ Failed to import flight_multi_agent: {e}")
        print("\nMake sure:")
        print("  1. flight_multi_agent.py is in the same directory")
        print("  2. All dependencies are installed")
        print("  3. .env file contains OPENAI_API_KEY")
        sys.exit(1)
    
    print()
    
    # Run tests
    for i, test_case in enumerate(TEST_PAYLOADS, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/{len(TEST_PAYLOADS)}: {test_case['name']}")
        print(f"{'=' * 80}")
        
        payload = test_case['payload']
        
        # Display test info
        print(f"\n📋 Test Payload:")
        print(f"   Prompt: {payload['prompt']}")
        print(f"   Session: {payload['session_id']}")
        print(f"   Window: {payload['end_timestamp'] - payload['start_timestamp']}s")
        print()
        
        # Invoke agent
        try:
            result = await invoke(payload)
            
            print(f"✅ Agent Response:")
            print(f"   {result.get('result', 'No result')}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("=" * 80)
    print("🎉 ALL TESTS COMPLETED")
    print("=" * 80)


async def interactive_test():
    """Interactive mode - ask questions manually"""
    
    print("=" * 80)
    print("💬 INTERACTIVE MODE")
    print("=" * 80)
    print()
    print("Type your questions (or 'quit' to exit)")
    print()

    import sys, os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from flight_multi_agent import invoke
    
    session_id = f"interactive-{int(datetime.now().timestamp())}"
    session_start = int(datetime.now(timezone.utc).timestamp())
    
    while True:
        try:
            user_input = input("\n🙋 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Create payload
            payload = {
                "prompt": user_input,
                "session_id": session_id,
                "start_timestamp": session_start,
                "end_timestamp": int(datetime.now(timezone.utc).timestamp())
            }
            
            # Invoke agent
            result = await invoke(payload)
            print(f"\n🤖 Agent: {result.get('result', 'No response')}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")


async def check_dynamodb_data():
    """Check if DynamoDB has data in the expected time window"""
    
    print("=" * 80)
    print("🔍 DYNAMODB DATA CHECK")
    print("=" * 80)
    print()
    
    import boto3
    
    dynamodb = boto3.client('dynamodb', region_name='eu-central-1')
    
    # Check raw-flights table
    print("📊 Checking raw-flights table...")
    try:
        response = dynamodb.describe_table(TableName='raw-flights')
        print(f"   ✅ Table exists: {response['Table']['TableName']}")
        print(f"   Item count: {response['Table']['ItemCount']}")
        
        # Check GSI
        gsi_names = [gsi['IndexName'] for gsi in response['Table'].get('GlobalSecondaryIndexes', [])]
        if 'FlightsByTime' in gsi_names:
            print(f"   ✅ GSI 'FlightsByTime' exists")
        else:
            print(f"   ❌ GSI 'FlightsByTime' NOT FOUND!")
            print(f"   Available GSIs: {gsi_names}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # Check agent-sessions table
    print("📊 Checking agent-sessions table...")
    try:
        response = dynamodb.describe_table(TableName='agent-sessions')
        print(f"   ✅ Table exists: {response['Table']['TableName']}")
        print(f"   Item count: {response['Table']['ItemCount']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # Query sample data from GSI
    print("📊 Querying recent data from FlightsByTime GSI...")
    try:
        end_time = int(datetime.now(timezone.utc).timestamp())
        start_time = end_time - 3600  # Last 1 hour
        
        response = dynamodb.query(
            TableName='raw-flights',
            IndexName='FlightsByTime',
            KeyConditionExpression='data_type = :pk AND #ts BETWEEN :start AND :end',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={
                ':pk': {'S': 'FLIGHTS'},
                ':start': {'N': str(start_time)},
                ':end': {'N': str(end_time)}
            },
            Limit=5
        )
        
        item_count = len(response.get('Items', []))
        print(f"   ✅ Found {item_count} items in last hour")
        
        if item_count > 0:
            print(f"   Sample item keys: {list(response['Items'][0].keys())}")
        else:
            print(f"   ⚠️  No data found in last hour. Is EC2 data generator running?")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()


def main():
    """Main entry point"""
    
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = "test"
    
    if mode == "interactive":
        asyncio.run(interactive_test())
    elif mode == "check":
        asyncio.run(check_dynamodb_data())
    else:
        asyncio.run(test_agent())


if __name__ == "__main__":
    print("""
Usage:
    python test_flight_agent_local.py           # Run automated tests
    python test_flight_agent_local.py interactive  # Interactive chat mode
    python test_flight_agent_local.py check       # Check DynamoDB data
    """)
    
    main()