
ARG REGION=eu-central-1
FROM 763104351884.dkr.ecr.${REGION}.amazonaws.com/tensorflow-training:2.6.0-cpu-py38-ubuntu20.04-v1.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
 && rm -rf /var/lib/apt/lists/*

# SageMaker'in beklediği klasörleri oluştur
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


# Kodları ve gereksinimleri yerleştir
COPY requirements.txt /opt/ml/code/
RUN pip install --upgrade pip && pip install -r /opt/ml/code/requirements.txt

COPY train.py inference.py wsgi.py nginx.conf start_server.py /opt/ml/code/

# Çalışma dizinini /opt/ml/code olarak ayarla
WORKDIR /opt/ml/code

EXPOSE 8080

ENTRYPOINT ["python", "start_server.py"]