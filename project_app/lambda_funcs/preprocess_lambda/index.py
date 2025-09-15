import os
import json
import sys
import boto3
import base64
import pandas as pd
import numpy as np
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

REGION = os.environ["REGION"]
PROCESSED_STREAM = os.environ["KINESIS_PROCESSED_STREAM_NAME"]

kinesis_client = boto3.client('kinesis', region_name= REGION)

def feature_engineering(df):
    logging.info("Starting feature engineering...")

    # ---------------------------
    # Derived features
    # ---------------------------
    df["distance_ratio_by_total"] = df.groupby("airline")["distance"].transform("sum") / df["distance"].sum()

    bins = [0, 500, 1000, np.inf]
    labels = ["0-500 miles", "500-1000 miles", "1000+ miles"]
    df["distance_category"] = pd.cut(df["distance"], bins=bins, labels=labels, ordered=True)
    df["distance_category"] = df["distance_category"].cat.codes

    df["daily_flight_count"] = df.groupby(["airline", "date"])["airline"].transform("count")

    airline_total_aircraft_count = df.groupby("airline")["tailnum"].nunique()
    df["aircraft_count_by_airline"] = df["airline"].map(airline_total_aircraft_count)

    # ---------------------------
    # Filter Columns - Keep all columns for store raw data in the kinesis stream
    # ---------------------------
    # corrs = ["air_time", "flight", "dewp", "wind_gust", "daily_flight_count"]
    # cat_with_high_card = ["tailnum", "dest", "route"]
    # date_features = ["dep_time", "sched_dep_time", "arr_time", "sched_arr_time", "date", "date_string"]
    # other_features = ["origin","carrier"] 
    # cols_will_be_not_used = corrs + cat_with_high_card + date_features + other_features

    # feature_columns = [col for col in df.columns if col not in cols_will_be_not_used]
    # df = df[feature_columns]

    # ---------------------------
    # One-hot encoding airline 
    # ---------------------------
    all_airlines = [
        "allegiant_air","american_airlines_inc","delta_air_lines_inc",
        "frontier_airlines_inc","hawaiian_airlines_inc","horizon_air",
        "jetblue_airways","skywest_airlines_inc","southwest_airlines_co",
        "spirit_air_lines","united_air_lines_inc"
    ]

    category_one_hot = pd.get_dummies(df["airline"]).astype(int)

    # Eksik kolonları ekle
    for col in all_airlines:
        if col not in category_one_hot.columns:
            category_one_hot[col] = 0

    # Kolon sırasını sabitle
    category_one_hot = category_one_hot[all_airlines]

    
    # df = df.drop("airline", axis=1) keep airline for store raw data in the kinesis stream
    df = pd.concat([df, category_one_hot], axis=1)

    logging.info(f"Final feature shape: {df.shape}")
    return df


def lambda_handler(event, context):
    records = []
    for r in event["Records"]:
        payload = base64.b64decode(r["kinesis"]["data"]).decode("utf-8")
        record = json.loads(payload)
        records.append(record)
    df = pd.DataFrame(records)
    df_processed = feature_engineering(df)
    
    for _, row in df_processed.iterrows():
        kinesis_client.put_record(
            StreamName=PROCESSED_STREAM,
            Data=json.dumps(row.to_dict()),
            PartitionKey=str(row.get("flight", "0"))
        )
    logger.info(f"Processed {len(df_processed)} records.")
    return {"status": "success"}
