FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/ml/input/config \
    && mkdir -p /opt/ml/input/data/train \
    && mkdir -p /opt/ml/input/data/validation \
    && mkdir -p /opt/ml/input/data/test \
    && mkdir -p /opt/ml/output \
    && mkdir -p /opt/ml/model \
    && mkdir -p /opt/ml/code \
    && mkdir -p /opt/ml/failure

ENV PYTHONUNBUFFERED=TRUE \
    PYTHONDONTWRITEBYTECODE=TRUE \
    DEBIAN_FRONTEND=noninteractive

ENV SM_CHANNEL_TRAIN=/opt/ml/input/data/train
ENV SM_CHANNEL_VALIDATION=/opt/ml/input/data/validation
ENV SM_OUTPUT_DATA_DIR=/opt/ml/output
ENV SM_MODEL_DIR=/opt/ml/model
ENV SM_USER_CODE_DIR=/opt/ml/code
ENV SM_CONFIG_DIR=/opt/ml/input/config
ENV SM_FAILURE_DIR=/opt/ml/failure


COPY requirements.txt /opt/ml/code/
RUN pip install --upgrade pip && pip install -r /opt/ml/code/requirements.txt --no-cache-dir
COPY train.py  /opt/ml/code/

WORKDIR /opt/ml/code

ENTRYPOINT ["python", "train.py"]