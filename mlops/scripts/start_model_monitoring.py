import os
import logging
from sagemaker.model_monitor import DefaultModelMonitor, CronExpressionGenerator
from sagemaker.session import Session
import boto3

# =============================================================================
# Logging Config
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# =============================================================================
# Environment Variables 
# =============================================================================
region = os.environ["REGION"]
sagemaker_role_arn = os.environ["SAGEMAKER_ROLE_ARN"]
endpoint_name = os.environ["ENDPOINT_NAME"]
baseline_statistics_uri = os.environ["BASELINE_STATISTICS_URI"]
baseline_constraints_uri = os.environ["BASELINE_CONSTRAINTS_URI"]
monitoring_output_path = os.environ["MONITORING_OUTPUT_PATH"]
monitor_name = os.environ["MONITOR_NAME"]
instance_type = os.environ["INSTANCE_TYPE"]
instance_count = int(os.environ.get("INSTANCE_COUNT", 1))
volume_size = int(os.environ.get("VOLUME_SIZE", 20))

# =============================================================================
# SageMaker Session & Monitor
# =============================================================================
sagemaker_session = Session(boto_session=boto3.session.Session(region_name=region))

monitor = DefaultModelMonitor(
    role=sagemaker_role_arn,
    instance_count=instance_count,
    instance_type=instance_type,
    volume_size_in_gb=volume_size,
    max_runtime_in_seconds=1800,
    sagemaker_session=sagemaker_session
)

monitor.create_monitoring_schedule(
    monitor_schedule_name=monitor_name,
    endpoint_input=endpoint_name,
    statistics=baseline_statistics_uri,
    constraints=baseline_constraints_uri,
    output_s3_uri=monitoring_output_path,
    schedule_cron_expression=CronExpressionGenerator.hourly(),
    enable_cloudwatch_metrics=True
)

logger.info("✅ Model Monitoring schedule created successfully.")
