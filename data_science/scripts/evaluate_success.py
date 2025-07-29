# copy_model.py
import shutil
import os
import logging


logging.basicConfig(level=logging.INFO)

src = "/opt/ml/processing/model"
dst = "/opt/ml/processing/final_model"

if not os.path.exists(src):
    logging.error(f"Source model directory does not exist: {src}")
    raise FileNotFoundError(f"Source model directory does not exist: {src}")

shutil.copytree(src, dst, dirs_exist_ok=True)
logging.info(f"Model copied from {src} to {dst}")