import numpy as np
import pandas as pd
import sys
import os
import logging
from sklearn.model_selection import train_test_split


BASE_DIR = "/opt/ml/processing"
INPUT_PATH = f"{BASE_DIR}/input/flights_sample.csv"
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

TRAIN_DIR = os.path.join(OUTPUT_DIR, "train")
VALIDATION_DIR = os.path.join(OUTPUT_DIR, "validation")
TEST_DIR = os.path.join(OUTPUT_DIR, "test")

# Combined dataset directory for final training job
COMBINED_DIR = os.path.join(OUTPUT_DIR, "combined")

# Baseline dataset directory for sagemaker model monitoring
BASELINE_DIR = os.path.join(OUTPUT_DIR, "baseline")

# ----------------------------------------
# Logging Setup
# ----------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ----------------------------------------
# Load the dataset
# ----------------------------------------
def load_data(file_path):
    logging.info(f"Loading dataset from {file_path}")
    if not os.path.exists(file_path):
        logging.error(f"Dataset not found: {file_path}")
        sys.exit(1)
    df = pd.read_csv(file_path, parse_dates=["dep_time", "sched_dep_time", "arr_time", "sched_arr_time", "date"])
    df["date_string"] = df["date_string"].astype(str)
    logging.info(f"Dataset shape: {df.shape}")
    return df


# ----------------------------------------
# Feature Engineering
# ----------------------------------------
def feature_engineering(df):
    logging.info("Starting feature engineering...")

    df["distance_ratio_by_total"] = df.groupby("airline")["distance"].transform("sum") / df["distance"].sum()

    bins = [0, 500, 1000, np.inf]
    labels = ["0-500 miles", "500-1000 miles", "1000+ miles"]
    df["distance_category"] = pd.cut(df["distance"], bins=bins, labels=labels, ordered=True)
    df["distance_category"] = df["distance_category"].cat.codes

    df["daily_flight_count"] = df.groupby(["airline", "date"])["airline"].transform("count")

    airline_delay_group = (
        df.groupby(["airline", "date"])
        .agg({"dep_delay": "sum", "arr_delay": "sum", "daily_flight_count": "mean"})
        .reset_index()
    )

    airline_delay_group["airline_daily_performance_kpi"] = (
        airline_delay_group["dep_delay"] + airline_delay_group["arr_delay"]
    ) / airline_delay_group["daily_flight_count"]
    airline_delay_group.drop(["dep_delay", "arr_delay", "daily_flight_count"], axis=1, inplace=True)
    df = df.merge(airline_delay_group, on=["airline", "date"], how="left")

    airline_total_aircraft_count = df.groupby("airline")["tailnum"].nunique()
    df["aircraft_count_by_airline"] = df["airline"].map(airline_total_aircraft_count)

    bins = [-np.inf, -10.0, -5.0, 0.0, 5.0, np.inf]
    labels = ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"]
    df["dep_delay_category"] = pd.cut(df["dep_delay"], bins=bins, labels=labels)
    df["dep_delay_category"] = df["dep_delay_category"].cat.codes

    date_string_column = ["date_string"]
    corrs = ["air_time", "flight", "dewp", "wind_gust", "daily_flight_count"]
    cat_with_high_card = [
        col for col in df.columns if df[col].nunique() > 80 and str(df[col].dtypes) in ["category", "object"]
    ]
    date_features = df.select_dtypes(include="datetime64").columns.to_list()
    other_features = ["carrier", "origin"]
    cols_will_be_not_used = corrs + cat_with_high_card + date_features + other_features + date_string_column

    feature_columns = [col for col in df.columns if col not in cols_will_be_not_used]
    df = df[feature_columns]

    category_one_hot = pd.get_dummies(df["airline"], drop_first=True).astype(int)
    df.drop("airline", axis=1, inplace=True)
    df = pd.concat([df, category_one_hot], axis=1)

    logging.info(f"Final feature shape: {df.shape}")
    return df


# ----------------------------------------
# Data Split and Save
# ----------------------------------------
def split_data(df, test_size=0.2, val_size=0.2, random_state=42, shuffle=True):
    logging.info("Splitting data into train, validation, and test sets...")
    df_train_val, df_test = train_test_split(df, test_size=test_size, random_state=random_state, shuffle=shuffle)
    val_ratio = val_size / (1 - test_size)
    df_train, df_val = train_test_split(df_train_val, test_size=val_ratio, random_state=random_state)
    return df_train, df_val, df_test


def save_data(train_df, val_df, test_df, output_dir):
    logging.info(f"Saving datasets to {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)

    dirs = ["train", "validation", "test", "combined", "baseline"]
    for d in dirs:
        os.makedirs(os.path.join(output_dir, d), exist_ok=True)
    
    train_df.to_csv(os.path.join(TRAIN_DIR, "train.csv"), index=False)
    val_df.to_csv(os.path.join(VALIDATION_DIR, "validation.csv"), index=False)
    test_df.to_csv(os.path.join(TEST_DIR, "test.csv"), index=False)
    
    # combined_df for final training job.
    combined_df = pd.concat([train_df, val_df], ignore_index=True)
    combined_df.to_csv(os.path.join(COMBINED_DIR, "train.csv"), index=False)
    
    # baseline_df for sagemaker model monitoring.
    baseline_df = combined_df.copy()
    baseline_df.to_csv(os.path.join(BASELINE_DIR, "baseline.csv"), index=False)
    
    logging.info(f"Train shape: {train_df.shape}")
    logging.info(f"Validation shape: {val_df.shape}")
    logging.info(f"Test shape: {test_df.shape}")
    logging.info(f"Combined df for final trainig job shape: {combined_df.shape}")
    logging.info(f"Baseline df for sagemaker model monitoring shape: {baseline_df.shape}")
    logging.info("Data saved successfully.")


# ----------------------------------------
# Main
# ----------------------------------------
def main():
    df = load_data(INPUT_PATH)
    df = feature_engineering(df)
    df_train, df_val, df_test = split_data(df)
    save_data(df_train, df_val, df_test, OUTPUT_DIR)


if __name__ == "__main__":
    main()
