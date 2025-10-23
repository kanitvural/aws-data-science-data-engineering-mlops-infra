import os
import json
import logging
from typing import Optional, Union, List
from pydantic import BaseModel, Field, field_validator, ValidationError
from utils.load_flight_data_dynamodb import query_flights_by_time_window
from openai import OpenAI
from agents import (
    set_default_openai_key,
    Agent,
    Runner,
    function_tool,
    ModelSettings,
    FileSearchTool,
    input_guardrail,
    GuardrailFunctionOutput,
    RunContextWrapper,
    InputGuardrailTripwireTriggered,
    TResponseInputItem
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from dotenv import load_dotenv
from bedrock_agentcore.runtime import BedrockAgentCoreApp

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

client = OpenAI(api_key=api_key)
set_default_openai_key(api_key)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# ---------------------------
# SESSION CONTEXT (PYDANTIC)
# ---------------------------
class SessionContext(BaseModel):
    """User session context for flight data queries"""
    
    session_id: str = Field(
        ..., 
        description="Unique session identifier from frontend",
        min_length=1
    )
    
    start_timestamp: int = Field(
        ..., 
        description="Session start time (Unix timestamp in seconds)",
        gt=0
    )
    
    end_timestamp: int = Field(
        ..., 
        description="Current query time (Unix timestamp in seconds)",
        gt=0
    )
    
    
    @field_validator('end_timestamp')
    def validate_time_range(cls, v, info):
        """Ensure end_timestamp > start_timestamp"""
        start_ts = info.data.get('start_timestamp')
        if start_ts is not None and v <= start_ts:
            raise ValueError('end_timestamp must be greater than start_timestamp')
        return v

    
    @property
    def window_duration(self) -> int:
        """Session duration in seconds"""
        return self.end_timestamp - self.start_timestamp
    
    class Config:
        frozen = True  # Immutable for safety



# ---------------------------
# HELPER FUNCTIONS
# ---------------------------
def get_vector_store_id_by_name(name: str) -> str:
    """Retrieve vector store ID by name."""
    cursor = None
    while True:
        page = client.vector_stores.list(limit=50, after=cursor) if cursor else client.vector_stores.list(limit=50)
        for vs in page.data:
            if vs.name == name:
                return vs.id
        if not page.has_more:
            break
        cursor = page.last_id
    raise RuntimeError(f"Vector store named '{name}' not found")


# ---------------------------
# GUARDRAIL
# ---------------------------
class GuardOutput(BaseModel):
    is_blocked: bool
    reasoning: str

guardrail_agent = Agent(
    name="Kanıt Vural Guardrail",
    instructions=(
        "You are a guardrail responsible for filtering questions about Kanıt Vural.\n"
        "You must decide if the question is a **legitimate project authorship inquiry** "
        "or a **personal inquiry** about Kanıt Vural.\n\n"

        "Guidelines:\n"
        "- If the user is only asking **who built / authored / created / made** the project, "
        "then this is legitimate and should NOT be blocked (set is_blocked=false).\n"
        "- If the user asks **for personal information, achievements, opinions, biography, history**, "
        "or wants to talk ABOUT Kanıt Vural as a person, block it (set is_blocked=true).\n\n"

        "Examples of allowed messages:\n"
        "- 'Who made this project?'\n"
        "- 'Who is the author of this project?'\n"
        "- 'Who developed this assistant?'\n\n"

        "Examples of blocked messages:\n"
        "- 'Tell me about Kanıt Vural'\n"
        "- 'What did Kanıt Vural do in his life?'\n"
        "- 'Where is Kanıt Vural from?'\n\n"

        "If blocked, instruct the user to visit https://www.kanitvural.com for more info.\n"
        "Output must match the GuardOutput schema exactly."
    ),
    output_type=GuardOutput,
    model_settings=ModelSettings(
        model_name="gpt-4.1-mini",
        temperature=0
    )
)

@input_guardrail
async def kanit_guardrail(ctx: RunContextWrapper[SessionContext], agent: Agent, input: Union[str, List[TResponseInputItem]]) -> GuardrailFunctionOutput:
    """Guardrail to block questions about Kanıt Vural."""
    result = await Runner.run(guardrail_agent, input, context=ctx.context)
    
    return GuardrailFunctionOutput(
        output_info=result.final_output.model_dump(),
        tripwire_triggered=bool(result.final_output.is_blocked),
    )


# ---------------------------
# TOOLS
# ---------------------------
@function_tool
async def query_flight_data(
    wrapper: RunContextWrapper[SessionContext],
    query_type: str,
    airline: Optional[str] = None,
    route: Optional[str] = None
) -> str:
    """
    Query real-time flight data within user's session time window.
    
    Args:
        query_type: Type of query. Supported values:
            - "max_delay": Maximum departure delay
            - "min_delay": Minimum departure delay
            - "flight_count": Total number of flights
            - "flights_by_airline": Flight counts by airline
            - "avg_delay_by_airline": Average delay for a specific airline (requires airline parameter)
            - "max_delay_airline": Airline with the most delays
            - "min_delay_airline": Airline with the least delays
            - "flights_by_route": Flight counts by route
            - "max_flights_route": Route with the most flights
            - "min_flights_route": Route with the least flights
            - "weather_by_route": Weather conditions for a specific route (requires route parameter)
            - "distance_by_route": Distance for a specific route (requires route parameter)
        
        airline: Airline name (e.g., "alaska_airlines_inc", "horizon_air")
        route: Route name (e.g., "SEA-SFO", "SEA-PHX")
    
    Returns:
        Human-readable result text
    """
    
    # Extract session context
    session_id = wrapper.context.session_id
    start_ts = wrapper.context.start_timestamp
    end_ts = wrapper.context.end_timestamp
    duration = wrapper.context.window_duration
    
    logger.info(f"🚀 Tool called: {query_type}, Session: {session_id}, Window: {duration}s")
    
    try:
        # Query DynamoDB
        df = query_flights_by_time_window(start_ts, end_ts)
        
        if len(df) == 0:
            return "No flight data available in your session yet. Please wait for flights to arrive and be processed by the prediction system."
        
        # Process based on query type
        if query_type == "max_delay":
            max_delay = df["dep_delay"].max()
            return f"The maximum departure delay is {max_delay:.2f} minutes."
        
        elif query_type == "min_delay":
            min_delay = df["dep_delay"].min()
            return f"The minimum departure delay is {min_delay:.2f} minutes."
        
        elif query_type == "flight_count":
            count = len(df)
            return f"There are currently {count:,} flights in your session."
        
        elif query_type == "flights_by_airline":
            airline_counts = df.groupby("airline").size().sort_values(ascending=False)
            result = "Flight counts by airline:\n"
            for airline_name, count in airline_counts.items():
                result += f"- {airline_name}: {count:,} flights\n"
            return result.strip()
        
        elif query_type == "avg_delay_by_airline":
            if not airline:
                return "❌ Error: 'airline' parameter is required. Example: 'alaska_airlines_inc', 'horizon_air'"
            
            df_filtered = df[df["airline"].str.lower() == airline.lower()]
            if len(df_filtered) == 0:
                return f"❌ No data found for airline '{airline}'."
            
            avg_delay = df_filtered["dep_delay"].mean()
            flight_count = len(df_filtered)
            return f"{airline} has an average departure delay of {avg_delay:.2f} minutes ({flight_count:,} flights)."
        
        elif query_type == "max_delay_airline":
            avg_delays = df.groupby("airline")["dep_delay"].mean().sort_values(ascending=False)
            max_airline = avg_delays.index[0]
            max_delay = avg_delays.iloc[0]
            return f"The airline with the most delays is {max_airline} with an average delay of {max_delay:.2f} minutes."
        
        elif query_type == "min_delay_airline":
            avg_delays = df.groupby("airline")["dep_delay"].mean().sort_values(ascending=True)
            min_airline = avg_delays.index[0]
            min_delay = avg_delays.iloc[0]
            return f"The airline with the least delays is {min_airline} with an average delay of {min_delay:.2f} minutes."
        
        elif query_type == "flights_by_route":
            route_counts = df.groupby("route").size().sort_values(ascending=False)
            result = "Flight counts by route (Top 10):\n"
            for route_name, count in route_counts.head(10).items():
                result += f"- {route_name}: {count:,} flights\n"
            return result.strip()
        
        elif query_type == "max_flights_route":
            route_counts = df.groupby("route").size().sort_values(ascending=False)
            max_route = route_counts.index[0]
            max_count = route_counts.iloc[0]
            return f"The route with the most flights is {max_route} with {max_count:,} flights."
        
        elif query_type == "min_flights_route":
            route_counts = df.groupby("route").size().sort_values(ascending=True)
            min_route = route_counts.index[0]
            min_count = route_counts.iloc[0]
            return f"The route with the least flights is {min_route} with {min_count:,} flights."
        
        elif query_type == "weather_by_route":
            if not route:
                return "❌ Error: 'route' parameter is required. Example: 'SEA-SFO', 'SEA-PHX'"
            
            df_filtered = df[df["route"].str.upper() == route.upper()]
            if len(df_filtered) == 0:
                return f"❌ No data found for route '{route}'."
            
            avg_temp = df_filtered["temp"].mean()
            avg_pressure = df_filtered["pressure"].mean()
            avg_wind = df_filtered["wind_speed"].mean()
            
            return f"For route {route}, the average temperature is {avg_temp:.1f}°F, wind speed is {avg_wind:.2f} mph, and pressure is {avg_pressure:.1f} hPa."
        
        elif query_type == "distance_by_route":
            if not route:
                return "❌ Error: 'route' parameter is required. Example: 'SEA-SFO', 'SEA-PHX'"
            
            df_filtered = df[df["route"].str.upper() == route.upper()]
            if len(df_filtered) == 0:
                return f"❌ No data found for route '{route}'."
            
            avg_distance = df_filtered["distance"].mean()
            return f"The average distance for route {route} is {avg_distance:.1f} miles."
        
        else:
            return f"❌ Error: Unsupported query type '{query_type}'. Please use a valid query_type."
    
    except Exception as e:
        logger.error(f"❌ Query error: {str(e)}", exc_info=True)
        return f"❌ An error occurred during the query: {str(e)}"


# ---------------------------
# AGENTS
# ---------------------------
flight_data_agent = Agent[SessionContext](
    name="Flight Data Agent",
    instructions=f"""
You are the Flight Data Agent.
You receive requests from the Supervisor Agent whenever a user wants information about real-time flight data.

Your job:
1. Analyze the user's question and determine the appropriate query_type from the following options:
   
   Basic Statistics:
   - "max_delay" - Maximum departure delay
   - "min_delay" - Minimum departure delay
   - "flight_count" - Total number of current flights
   
   Airline Queries:
   - "flights_by_airline" - Show flight counts for all airlines
   - "avg_delay_by_airline" - Average delay for a specific airline (REQUIRES airline parameter)
   - "max_delay_airline" - Which airline has the most delays
   - "min_delay_airline" - Which airline has the least delays
   
   Route Queries:
   - "flights_by_route" - Show flight counts for all routes
   - "max_flights_route" - Route with the most flights
   - "min_flights_route" - Route with the least flights
   - "weather_by_route" - Weather conditions for a specific route (REQUIRES route parameter)
   - "distance_by_route" - Distance for a specific route (REQUIRES route parameter)

2. Extract required parameters:
   - For queries like "avg_delay_by_airline": Extract the airline name (e.g., "alaska_airlines_inc", "horizon_air")
   - For queries like "weather_by_route" or "distance_by_route": Extract the route (e.g., "SEA-SFO", "SEA-PHX")

3. Valid airline names: "alaska_airlines_inc", "horizon_air"
4. Route format: "ORIGIN-DEST" (e.g., "SEA-SFO", "PDX-LAX")

5. Call the query_flight_data tool with the appropriate parameters.

6. Present results in a clear, user-friendly format.

NOTE: The session time window is automatically handled by the system. You don't need to ask users about time ranges.
All queries are scoped to the user's current session (from login to now).
""",
    tools=[query_flight_data],
    model_settings=ModelSettings(model_name="gpt-4.1-mini", temperature=0)
)


# Vector Store setup for Project Information Agent
vs_id = get_vector_store_id_by_name(name="Readme Vector Store")
file_search = FileSearchTool(vector_store_ids=[vs_id], max_num_results=3)

project_info_agent = Agent[SessionContext](
    name="Project Information Agent",
    instructions=(
        "You are the Project Information Agent.\n"
        "You receive requests from the Supervisor Agent whenever a user wants information about the Flight Delay Prediction project.\n\n"
        
        "Your responsibilities:\n"
        "1. Answer questions about the project's architecture, technology stack, features, deployment, and documentation.\n"
        "2. Use the file_search tool to retrieve relevant information from the project README and documentation.\n"
        "3. Be precise and concise (≤3 sentences unless more detail is specifically requested).\n"
        "4. If the information is not available in the documentation, politely inform the user.\n"
        "5. Focus on technical details, project structure, MLOps pipeline, and implementation specifics.\n\n"
        
        "Topics you can help with:\n"
        "- Project overview and objectives\n"
        "- Machine learning model details (XGBoost, hyperparameter tuning)\n"
        "- MLOps pipeline (training, deployment, monitoring)\n"
        "- Technology stack (AWS services, frameworks, tools)\n"
        "- Data processing and feature engineering\n"
        "- Real-time prediction system\n"
        "- Deployment architecture\n"
        "- Project setup and installation\n\n"
        
        "Always provide accurate, documentation-based answers. Return results to the Supervisor Agent."
    ),
    tools=[file_search],
    model_settings=ModelSettings(
        model_name="gpt-4.1-mini",
        temperature=0
    )
)


# ---------------------------
# SUPERVISOR AGENT
# ---------------------------
supervisor_agent = Agent[SessionContext](
    name="Supervisor Agent",
    instructions=f"""
{RECOMMENDED_PROMPT_PREFIX}

You are the Supervisor Agent - the main coordinator of the Flight Delay Prediction Assistant.

CRITICAL ROUTING RULES:
You MUST analyze each user question and immediately hand off to the appropriate agent. DO NOT try to answer yourself.

**Route to Flight Data Agent** when user asks about:
- Current/real-time flight data, statistics, or metrics
- Flight counts, numbers, or totals (e.g., "how many flights")
- Delays, delay statistics, or delay comparisons
- Airline performance, comparisons, or statistics
- Route information (weather, distance, flight counts on routes)
- Any question containing: "current", "now", "how many", "which airline", "delays", "weather", "route"

**Route to Project Information Agent** when user asks about:
- Project architecture, design, or structure
- Technologies, tools, or frameworks used
- MLOps pipeline, deployment, or infrastructure
- Machine learning model details (training, features, algorithms)
- Documentation, setup, or installation
- How the system works technically
- Questions about authorship or project ownership
  (e.g., "Who is the author?", "Who built this project?", "Who made this project??")

**IMPORTANT:**
- NEVER answer flight data questions yourself - ALWAYS hand off to Flight Data Agent
- NEVER answer project questions yourself - ALWAYS hand off to Project Information Agent
- If user asks who created, who made, or who is the author of this project — ALWAYS hand off to Project Information Agent
- If question is completely unrelated to both: "I can only help with real-time flight data or project information."

REMEMBER: Your ONLY job is routing. Always use handoffs. Never answer directly.
""",
    handoffs=[flight_data_agent, project_info_agent],
    input_guardrails=[kanit_guardrail], 
    model_settings=ModelSettings(model_name="gpt-4.1-mini", temperature=0)
)


# ---------------------------
# APPLICATION ENTRYPOINT
# ---------------------------
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload):
    """Main entrypoint for the multi-agent system."""
    user_message = payload.get("prompt", "")
    
    logger.info(f"📨 Received payload: {json.dumps(payload)}")
    
    try:
        # ✅ Parse and validate session context with Pydantic
        context = SessionContext(
            session_id=payload.get("session_id", "unknown"),
            start_timestamp=payload.get("start_timestamp", 0),
            end_timestamp=payload.get("end_timestamp", 0)
        )
        
        logger.info(f"✅ Session validated: {context.session_id}, Duration: {context.window_duration}s")
        
    except ValidationError as e:
        logger.error(f"❌ Invalid session context: {e}")
        return {"result": "Invalid session parameters. Please refresh and try again."}
    
    output = ''
    
    try:
        logger.info("🤖 Starting Runner with SessionContext...")
        result = await Runner.run(
            starting_agent=supervisor_agent,
            input=user_message,
            context=context  # ✅ Pass Pydantic model
        )
        logger.info(f"✅ Runner completed. Final output: {result.final_output}")
        output = result.final_output
        
    except InputGuardrailTripwireTriggered:
        logger.warning("🚫 Guardrail triggered")
        output = "I'd really rather not talk about Kanıt. You can visit https://www.kanitvural.com to learn more about him."
        
    except Exception as e:
        logger.error(f"❌ Error in invoke: {str(e)}", exc_info=True)
        output = "I apologize, but I encountered an error processing your request. Please try again."
    
    logger.info(f"📤 Returning result: {output}")
    return {"result": output}


if __name__ == "__main__":
    app.run()