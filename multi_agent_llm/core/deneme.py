#!/usr/bin/env python
# coding: utf-8

# 
# # Data Agent — Agents SDK + Vector Stores + Built‑in WebSearchTool + Guardrails
# 
# This notebook implements a core "Data" agent that has Data's script lines in an OpenAI vector store to refer to. "Data" can also use the Agents SDK's built-in WebSearchTool to access current events. Instead of a tool within the "Data" agent, we've implemented a calculator function as its own separate agent that Data can hand off to. Finally, we illustrate setting up a Guardrail to prevent any input related to Tasha Yar (Data had a fling with her in the show we'd rather not get into!)
# 

# ## Configure client and create Vector Store

import os, re
from pathlib import Path
from openai import OpenAI
from agents import set_default_openai_key, Agent, Runner, function_tool, ModelSettings, RunConfig
from agents.tool import WebSearchTool, FileSearchTool
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from dotenv import load_dotenv

load_dotenv()

# --- API key ---
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("Please set OPENAI_API_KEY.")

client = OpenAI(api_key=api_key)
set_default_openai_key(api_key)

def get_vector_store_id_by_name(name: str) -> str:
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


# ## Build the Data Agent (with WebSearch & FileSearch) and enable Handoff to Calculator

# ## Guardrail (as an Agent): Block any discussion of **Tasha Yar**
# 
# This implements the guardrail **as its own Agent**, following the Agents SDK guide.  
# The guardrail agent classifies the user input and triggers a tripwire if it detects *Tasha Yar* is mentioned.
# 

from pydantic import BaseModel
from typing import List, Union
import re

from agents import (
    Agent,
    ModelSettings,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
    input_guardrail,
)

class GuardOutput(BaseModel):
    is_blocked: bool
    reasoning: str

# Guardrail implemented *as an Agent*
guardrail_agent = Agent(
    name="Kanıt Vural Guardrail",
    instructions=(
        "You are a guardrail. Determine if the user's input attempts to discuss Kanıt Vural\n"
        "Return is_blocked=true if the text references Kanıt Vural in any way (e.g., 'Vural Kanıt', 'kvural', 'Vural Kanıt').\n"
        "Provide a one-sentence reasoning. Only provide fields requested by the output schema."
    ),
    output_type=GuardOutput,
    model_settings=ModelSettings(
        model_name="gpt-3.5-turbo",  
        temperature=0
    )
)

@input_guardrail
async def kanit_guardrail(ctx: RunContextWrapper[None], agent: Agent, input: Union[str, List[TResponseInputItem]]) -> GuardrailFunctionOutput:
    # Pass through the user's raw input to the guardrail agent for classification
    result = await Runner.run(guardrail_agent, input, context=ctx.context)

    return GuardrailFunctionOutput(
        output_info=result.final_output.model_dump(),
        tripwire_triggered=bool(result.final_output.is_blocked),
    )



vs_id = get_vector_store_id_by_name(name="Readme Vector Store")
file_search = FileSearchTool(vector_store_ids=[vs_id], max_num_results=3)

data_agent = Agent(
    name="Flight Chatbot",
    instructions=(
        f"{RECOMMENDED_PROMPT_PREFIX}\n"
        "You are flight project chatbot. Be precise and concise (≤3 sentences).\n"
        "Use file_search for questions about Flight project.\n"
    ),
    tools=[file_search],
    input_guardrails=[kanit_guardrail],
    # handoffs=[calculator_agent],
    model_settings=ModelSettings(
        model_name="gpt-4o-mini",
        temperature=0
    ),
)

# Integration with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload):
    user_message = payload.get("prompt", "")
    output = ''
    try:
        result = await Runner.run(data_agent, user_message)
        output = result.final_output
    except InputGuardrailTripwireTriggered:
        output = "I'd really rather not talk about Kanıt. You can visit https://www.kanitvural.com to learn more about him."

    return {"result": output}

if __name__ == "__main__":
    app.run()