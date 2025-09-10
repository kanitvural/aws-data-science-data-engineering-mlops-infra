import os
import boto3
import pandas as pd
import json
import logging
from sagemaker.session import Session
from sagemaker.clarify import SageMakerClarifyProcessor, DataConfig, ModelConfig, SHAPConfig

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
bucket = os.environ["BUCKET"]
model_package_arn = os.environ["MODEL_PACKAGE_ARN"]
role = os.environ["SAGEMAKER_ROLE_ARN"]
shap_output_path = os.environ["SHAP_OUTPUT_PATH"]
shap_job_name = os.environ["SHAP_JOB_NAME"]
processed_data_key = os.environ["PROCESSED_DATA_KEY"]
endpoint_name = os.environ["ENDPOINT_NAME"]
target_column = os.environ["TARGET_COLUMN"]
instance_type = os.environ["INSTANCE_TYPE"]
instance_count = int(os.environ["INSTANCE_COUNT"])


sagemaker_session = Session(boto_session=boto3.session.Session(region_name=region))
s3_client = boto3.client('s3', region_name=region)

logger.info(f"🚀 Starting SHAP Analysis")

# =============================================================================
# 1. Get Feature Names from Baseline Constraints
# =============================================================================

try:
    constraints_obj = s3_client.get_object(Bucket=bucket, Key="baseline_report/constraints.json")
    constraints_data = json.loads(constraints_obj['Body'].read().decode('utf-8'))
    feature_names = [f['name'] for f in constraints_data['features'] if f['name'] != target_column]

    logger.info(f"✅ Loaded {len(feature_names)} feature names (excluding target: {target_column})")
    logger.debug(f"Feature names: {feature_names}")

except Exception as e:
    logger.error(f"❌ Error reading constraints.json: {e}")
    exit(1)

# =============================================================================
# 2. Load Data from Data Capture 
# =============================================================================
capture_data = []
prefix = f"data-capture/{endpoint_name}/AllTraffic/"

resp = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/')
years = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]

for year_prefix in years:
    resp_months = s3_client.list_objects_v2(Bucket=bucket, Prefix=year_prefix, Delimiter='/')
    months = [m['Prefix'] for m in resp_months.get('CommonPrefixes', [])]

    for month_prefix in months:
        resp_days = s3_client.list_objects_v2(Bucket=bucket, Prefix=month_prefix, Delimiter='/')
        days = [d['Prefix'] for d in resp_days.get('CommonPrefixes', [])]

        for day_prefix in days:
            resp_hours = s3_client.list_objects_v2(Bucket=bucket, Prefix=day_prefix, Delimiter='/')
            hours = [h['Prefix'] for h in resp_hours.get('CommonPrefixes', [])]

            for hour_prefix in hours:
                resp_files = s3_client.list_objects_v2(Bucket=bucket, Prefix=hour_prefix)
                if 'Contents' not in resp_files:
                    continue

                jsonl_files = [obj['Key'] for obj in resp_files['Contents'] if obj['Key'].endswith('.jsonl')]
                logger.info(f"📁 Found {len(jsonl_files)} JSONL files in {hour_prefix}")

                for key in jsonl_files:
                    try:
                        obj = s3_client.get_object(Bucket=bucket, Key=key)
                        for line in obj['Body'].read().decode('utf-8').strip().split('\n'):
                            if line:
                                capture_data.append(json.loads(line))
                    except Exception as e:
                        logger.warning(f"⚠️ Error reading {key}: {e}")

logger.info(f"✅ Loaded {len(capture_data)} data capture records")

# =============================================================================
# 3. Parse Data Capture Format and Create DataFrame
# =============================================================================
parsed_data = []

for record in capture_data:
    try:
        input_data = record['captureData']['endpointInput']['data'].strip()
        input_values = input_data.split(',')

        output_data = record['captureData']['endpointOutput']['data'].strip()
        prediction = float(output_data)

        if len(input_values) == len(feature_names):
            feature_dict = {}
            for i, name in enumerate(feature_names):
                try:
                    feature_dict[name] = float(input_values[i])
                except ValueError:
                    feature_dict[name] = input_values[i]

            feature_dict[target_column] = prediction
            feature_dict['inference_time'] = record['eventMetadata']['inferenceTime']
            feature_dict['event_id'] = record['eventMetadata']['eventId']

            parsed_data.append(feature_dict)
        else:
            logger.warning(f"⚠️ Input length mismatch: expected {len(feature_names)}, got {len(input_values)}")

    except Exception as e:
        logger.warning(f"⚠️ Error parsing record: {e}")
        continue

df_captured = pd.DataFrame(parsed_data)
logger.info(f"✅ Parsed {len(df_captured)} records from data capture")
logger.debug(f"Sample columns: {list(df_captured.columns)}")

# =============================================================================
# 4. Prepare features for SHAP
# =============================================================================
df_clean = df_captured.dropna()
logger.info(f"📊 Cleaned data: {len(df_clean)} records (removed {len(df_captured) - len(df_clean)} NaN rows)")

df_for_shap = df_clean.drop(columns=['inference_time', 'event_id'])
df_for_shap.to_csv(f"s3://{bucket}/{processed_data_key}", index=False)
logger.info(f"💾 Processed data saved to: s3://{bucket}/{processed_data_key}")

# =============================================================================
# 5. SHAP Explainability Analysis
# =============================================================================
clarify_processor = SageMakerClarifyProcessor(
    role=role,
    instance_count= instance_count,
    instance_type=instance_type,
    sagemaker_session=sagemaker_session
)

headers = df_for_shap.columns.to_list()
feature_cols = [col for col in headers if col != target_column]

shap_data_config = DataConfig(
    s3_data_input_path=f"s3://{bucket}/{processed_data_key}",
    s3_output_path=shap_output_path,
    label=target_column,
    headers=headers,
    dataset_type="text/csv"
)

model_config = ModelConfig(
    endpoint_name=endpoint_name,
    content_type="text/csv",
    accept_type="application/json"
)

baseline_values = df_for_shap[feature_cols].mean().fillna(0).tolist()

shap_config = SHAPConfig(
    baseline=[baseline_values],
    num_samples=10,
    agg_method="mean_abs"
)

clarify_processor.run_explainability(
    data_config=shap_data_config,
    model_config=model_config,
    explainability_config=shap_config,
    job_name=shap_job_name,
    wait=False,
    logs=False
)

logger.info(f"✅ SHAP job started: {shap_job_name}")
logger.info(f"📁 Results will be saved to: {shap_output_path}")

# =============================================================================
# 6. Data Quality Summary
# =============================================================================
logger.info("\n📈 Data Quality Summary:")
logger.info(f"Total records processed: {len(df_captured)}")
logger.info(f"Records after cleaning: {len(df_clean)}")
logger.info(f"Features used for SHAP: {len(feature_cols)}")
logger.info(f"Prediction range: {df_clean[target_column].min():.2f} to {df_clean[target_column].max():.2f}")
