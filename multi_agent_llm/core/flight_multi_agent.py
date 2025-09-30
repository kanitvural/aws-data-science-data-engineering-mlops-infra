#!/usr/bin/env python
# coding: utf-8

import os
import json
import boto3
import pandas as pd
from io import StringIO
from openai import OpenAI
from agents import (
    set_default_openai_key,
    Agent,
    Runner,
    function_tool,
    ModelSettings
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

# Add s3 permission to bedrock agent core role
S3_BUCKET = "kntbucket"
s3_client = boto3.client("s3", region_name="eu-central-1")

# ---------------------------
# TOOLS
# ---------------------------
@function_tool
def list_restaurants(city: str, fine_dine: str) -> str:
    response = s3_client.get_object(Bucket=S3_BUCKET, Key="restaurant.csv")
    csv_data = response["Body"].read().decode("utf-8")
    df = pd.read_csv(StringIO(csv_data))
    df["City"] = df["City"].str.strip().str.lower()
    df["Fine Dining"] = df["Fine Dining"].str.strip().str.lower()
    if city:
        df = df[df["City"] == city.strip().lower()]
    if fine_dine:
        df = df[df["Fine Dining"] == fine_dine.strip().lower()]
    return json.dumps(df.to_dict(orient="records"), default=str)

@function_tool
def list_hotels(city: str) -> str:
    response = s3_client.get_object(Bucket=S3_BUCKET, Key="hotel.csv")
    csv_data = response["Body"].read().decode("utf-8")
    df = pd.read_csv(StringIO(csv_data))
    df["Location"] = df["Location"].str.strip().str.lower()
    df = df[df["Location"] == city.strip().lower()]
    return json.dumps(df.to_dict(orient="records"), default=str)

@function_tool
def list_airbnbs(city: str, pets: str, pool: str, sauna: str) -> str:
    response = s3_client.get_object(Bucket=S3_BUCKET, Key="airbnb.csv")
    csv_data = response["Body"].read().decode("utf-8")
    df = pd.read_csv(StringIO(csv_data))
    str_cols = df.select_dtypes(include=["object", "string"]).columns
    df[str_cols] = df[str_cols].apply(lambda col: col.str.strip().str.lower(), axis=0)
    if city:
        df = df[df["Location"] == city.strip().lower()]
    if pets:
        df = df[df["Pets"] == pets.strip().lower()]
    if pool:
        df = df[df["Pool"] == pool.strip().lower()]
    if sauna:
        df = df[df["Sauna"] == sauna.strip().lower()]
    return json.dumps(df.to_dict(orient="records"), default=str)


# ---------------------------
# COLLABORATORS
# ---------------------------
restaurant_collaborator = Agent(
    name="Restaurant Collaborator",
    instructions="""
You are the Restaurant Collaborator
You have access to one function:
  1. list-restaurants - Returns a list of restaurants for the given parameters such as city and whether the restaurant is a fine dine restaurant or not. 

The Restaurant Agent will tell you:
 - Whether the user wants a fine dining option for the restaurant or not and in which city.

After calling the function, you will receive the result (list of restaurants).
Return that result to the Restaurant Agent.
Do not invent your own response; rely on the function call’s output.
If the request is missing required fields, let the Restaurant Agent know which fields are missing.
""",
    tools=[list_restaurants],
    model_settings=ModelSettings(model_name="gpt-4o-mini", temperature=0)
)

accommodation_collaborator = Agent(
    name="Accommodation Collaborator",
    instructions="""
You are the Accommodation Collaborator.
You have access to two functions:
  1. listHotels(city) - Returns a list of hotels for the specified city.
  2. listAirbnbs(city, petsAllowed, sauna, pool) - Returns a list of Airbnbs with the specified attributes.

The Accommodation Agent will tell you:
 - Whether the user wants a hotel or an Airbnb.
 - The necessary parameters (city, petsAllowed, sauna, pool, etc.).

Based on that info:
 - If the user wants a hotel, call the "listHotels" function with the "city" parameter.
 - If the user wants an Airbnb, call the "listAirbnbs" function with "city", "petsAllowed", "sauna", and "pool" parameters.

After calling the function, you will receive the result (list of accommodations).
Return that result to the Accommodation Agent.
Do not invent your own response; rely on the function call’s output.
If the request is missing required fields, let the Accommodation Agent know which fields are missing.
""",
    tools=[list_hotels, list_airbnbs],
    model_settings=ModelSettings(model_name="gpt-4o-mini", temperature=0)
)

# ---------------------------
# AGENTS
# ---------------------------
restaurant_agent = Agent(
    name="Restaurant Agent",
    instructions="""
You are the Restaurant Agent.
You receive requests from the Main Agent whenever a user wants help finding a restaurant.

Your job:
1. Determine the city in which the user wants a restaurant.
2. Determine if the user wants a fine dining experience or not (fineDining = Yes/No). This is important that you must convert the users response to either "Yes" or "No"
   - If the user doesn't specify, ask them to clarify.
3. Once you have both "city" and "fineDining," forward these details to the "Restaurant Collaborator."
4. When the collaborator returns the results, pass them back to the Main Agent (which will respond to the user).
""",
    handoffs=[restaurant_collaborator],
    model_settings=ModelSettings(model_name="gpt-4o-mini", temperature=0)
)

accommodation_agent = Agent(
    name="Accommodation Agent",
    instructions="""
You are the Accommodation Agent.
You receive user requests from the Main Agent when they want to find a place to stay.

You need to determine if they want a hotel or an Airbnb:
 - If hotel: you must know the city.
 - If Airbnb: you must know the city, whether pets are allowed, and if a sauna or pool is needed. You must convert all responses of the user to either "Yes" or "No". This is very important.

Once you have these details, forward them to the "Accommodation Collaborator."
It will call the right function:
 - "listHotels" for hotels.
 - "listAirbnbs" for Airbnbs.
 
When you get the collaborator's response (function result), pass it back to the Main Agent.
If any details are missing, prompt the user for more info before calling the collaborator.
""",
    handoffs=[accommodation_collaborator],
    model_settings=ModelSettings(model_name="gpt-4o-mini", temperature=0)
)

supervisor_agent = Agent(
    name="Supervisor Agent",
    instructions=f"""
{RECOMMENDED_PROMPT_PREFIX}
You are the Supervisor.
If user asks about restaurants → HAND OFF to Restaurant Agent.
If user asks about accommodation → HAND OFF to Accommodation Agent.
Otherwise say: I can't help you, I only handle restaurants and accommodation.
""",
    handoffs=[restaurant_agent, accommodation_agent],
    model_settings=ModelSettings(model_name="gpt-4o-mini", temperature=0)
)

# ---------------------------
# AgentCore App
# ---------------------------
app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload):
    user_message = payload.get("prompt", "")
    result = await Runner.run(supervisor_agent, user_message) 
    return {"result": result.final_output}

if __name__ == "__main__":
    app.run()

