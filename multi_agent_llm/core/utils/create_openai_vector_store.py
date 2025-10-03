# ## Configure client and create Vector Store

import os, re
from pathlib import Path
from openai import OpenAI
from agents import set_default_openai_key
from dotenv import load_dotenv

load_dotenv()

 

# --- API key ---
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("Please set OPENAI_API_KEY.")

client = OpenAI(api_key=api_key)
set_default_openai_key(api_key)

# # # --- Prepare small sample corpus for Lt. Commander Data ---
CORPUS_PATH = "../data/README.md"

# # --- Create a transient vector store and upload corpus ---
vs = client.vector_stores.create(name="Readme Vector Store")

# 1) Upload to Files API
uploaded = client.files.create(
    file=open(CORPUS_PATH, "rb"),
    purpose="assistants",                # important
)

# 2) Attach & poll on the vector store
vs_file = client.vector_stores.files.create_and_poll(
    vector_store_id=vs.id,
    file_id=uploaded.id,
)
print("vs_file.status:", vs_file.status)
print("vs_file.last_error:", getattr(vs_file, "last_error", None))

# # --- Function to delete the created Vector Store ---
# def delete_vector_store(vector_store_id: str):
#     """Delete a vector store by its ID"""
#     resp = client.vector_stores.delete(vector_store_id)
#     print(f"Deleted Vector Store {vector_store_id}: {resp}")


# # Example: delete the one we just created
# delete_vector_store(vs.id)