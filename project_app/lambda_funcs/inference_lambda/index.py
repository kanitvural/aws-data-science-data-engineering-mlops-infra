import os
import json
import sys
import boto3
import base64
import logging
import pandas as pd
import io

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

region = os.environ["REGION"]
predicted_stream = os.environ["KINESIS_PREDICTED_STREAM_NAME"]
sagemaker_endpoint = os.environ["ENDPOINT_NAME"]

kinesis_client = boto3.client("kinesis", region_name=region)
sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=region)

cols = [
    "year","month","day","arr_delay","distance","hour","minute","temp","humid",
    "wind_dir","wind_speed","precip","pressure","visib","distance_ratio_by_total",
    "distance_category","aircraft_count_by_airline","allegiant_air","american_airlines_inc",
    "delta_air_lines_inc","frontier_airlines_inc","hawaiian_airlines_inc","horizon_air","jetblue_airways",
    "skywest_airlines_inc","southwest_airlines_co","spirit_air_lines","united_air_lines_inc"
]

numeric_cols = [
    "arr_delay","distance","hour","minute","temp","humid",
    "wind_dir","wind_speed","precip","pressure","visib",
    "distance_ratio_by_total","distance_category","aircraft_count_by_airline"
]

categorical_cols = list(set(cols) - set(numeric_cols))


def lambda_handler(event, context):
    for r in event["Records"]:
        payload = base64.b64decode(r["kinesis"]["data"]).decode("utf-8")
        record = json.loads(payload)

        df = pd.DataFrame([record])

        numeric_existing = [c for c in numeric_cols if c in df.columns]
        df[numeric_existing] = df[numeric_existing].astype(float)

        for c in categorical_cols:
            if c not in df.columns:
                df[c] = 0
        df[categorical_cols] = df[categorical_cols].astype(int)

        df = df[cols]

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, header=False, index=False)
        csv_data = csv_buffer.getvalue()

        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=sagemaker_endpoint,
            ContentType="text/csv",
            Body=csv_data
        )

        result_str = response["Body"].read().decode("utf-8")
        prediction_df = pd.read_csv(io.StringIO(result_str), header=None)
        dep_delay_pred = float(prediction_df.iloc[0, 0])

        record["dep_delay"] = dep_delay_pred

        kinesis_client.put_record(
            StreamName=predicted_stream,
            Data=json.dumps(record),
            PartitionKey=str(record.get("flight", "0"))
        )
        logger.info(f"Predicted flight {record.get('flight')} with dep_delay={record.get('dep_delay')}")

    return {"status": "success"}

