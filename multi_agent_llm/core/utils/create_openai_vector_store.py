# ## Configure client and create Vector Store

import os, re, logging, time
from pathlib import Path
from openai import OpenAI
from agents import set_default_openai_key
from dotenv import load_dotenv

load_dotenv()

# --- Setup logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- API key ---
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("Please set OPENAI_API_KEY.")

client = OpenAI(api_key=api_key)
set_default_openai_key(api_key)

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "../../data/README.md")
VS_NAME = "Readme Vector Store"

# Delete old vector stores (to keep document always up-to-date)
existing_stores = client.vector_stores.list()
for store in existing_stores.data:
    if store.name == VS_NAME:
        client.vector_stores.delete(store.id)
        logger.info(f"🗑️ Deleted old vector store: {store.id}")

# Create new vector store
vs = client.vector_stores.create(name=VS_NAME)
logger.info(f"✅ Created new vector store: {vs.id}")

# 1) Upload to Files API
uploaded = client.files.create(
    file=open(CORPUS_PATH, "rb"),
    purpose="assistants",
)
logger.info(f"✅ File uploaded: {uploaded.id}")

# 2) Attach to vector store
client.vector_stores.files.create(
    vector_store_id=vs.id,
    file_id=uploaded.id,
)
logger.info(f"⏳ File attached, waiting for processing...")

# 3) Wait and check status
for i in range(10):
    time.sleep(3)
    vs_file = client.vector_stores.files.retrieve(
        vector_store_id=vs.id,
        file_id=uploaded.id
    )
    
    if vs_file.status == "completed":
        logger.info(f"✅ SUCCESS! File processed and ready to use")
        break
    elif vs_file.status == "failed":
        logger.error(f"❌ FAILED: {vs_file.last_error}")
        break
    else:
        logger.info(f"⏳ Still processing... ({vs_file.status})")

logger.info(f"📂 Final status: {vs_file.status}")
logger.info(f"🎯 Vector Store ID: {vs.id}")

# # --- Function to delete the created Vector Store ---
# def delete_vector_store(vector_store_id: str):
#     """Delete a vector store by its ID"""
#     resp = client.vector_stores.delete(vector_store_id)
#     logger.info(f"🗑️ Deleted Vector Store {vector_store_id}: {resp}")

# # Example: delete the one we just created
# delete_vector_store(vs.id)