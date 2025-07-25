import numpy as np
import pandas as pd
import sys
import os
import logging
import argparse
from sklearn.model_selection import train_test_split

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
    df = pd.read_csv(file_path)
    logging.info(f"Dataset shape: {df.shape}")
    return df

# ----------------------------------------
# Data Cleaning Functions
# ----------------------------------------
def drop_missing_values(df):
    logging.info("Dropping missing values...")
    df.dropna(subset=["dep_time", "dep_delay", "arr_time", "arr_delay", "air_time"], how="all", inplace=True)
    df.dropna(subset=["arr_time", "arr_delay", "air_time"], inplace=True)
    return df

def clean_time_columns(df):
    logging.info("Cleaning time columns...")
    df["date"] = pd.to_datetime(df[["year", "month", "day"]])
    df["date_string"] = df["date"].astype(str).str.replace("-", "")

    df["dep_time"] = df["dep_time"].astype(int).astype(str).str.zfill(4)
    df["sched_dep_time"] = df["sched_dep_time"].astype(str).str.zfill(4)
    df["arr_time"] = df["arr_time"].astype(int).astype(str).str.zfill(4)
    df["sched_arr_time"] = df["sched_arr_time"].astype(str).str.zfill(4)

    df["sched_dep_time"] = df["date_string"].str.cat(df["sched_dep_time"])
    df["sched_dep_time"] = pd.to_datetime(df["sched_dep_time"], format="%Y%m%d%H%M")

    df["sched_arr_time"] = df["date_string"].str.cat(df["sched_arr_time"])
    df["sched_arr_time"] = pd.to_datetime(df["sched_arr_time"], format="%Y%m%d%H%M")

    df["dep_time"] = df["dep_time"].replace({"2400": "0000"})
    df["dep_time"] = df["date_string"].str.cat(df["dep_time"])
    df["dep_time"] = pd.to_datetime(df["dep_time"], format="%Y%m%d%H%M")
    df.loc[df["dep_time"].dt.hour == 0, "dep_time"] += pd.Timedelta(days=1)

    df["arr_time"] = df["arr_time"].replace({"2400": "0000"})
    df["arr_time"] = df["date_string"].str.cat(df["arr_time"])
    df["arr_time"] = pd.to_datetime(df["arr_time"], format="%Y%m%d%H%M")
    df.loc[df["arr_time"].dt.hour == 0, "arr_time"] += pd.Timedelta(days=1)

    return df

def fill_missing_wind_data(df):
    logging.info("Filling missing wind data...")
    df = df.sort_values("dep_time").reset_index(drop=True)
    if len(df) > 10:
        df = df[:-10]

    wind_data_to_be_filled = ["wind_dir", "wind_speed", "wind_gust"]
    for value in wind_data_to_be_filled:
        df[value]=df[value].ffill()
    return df

def clean_inconsistent_features(df):
    logging.info("Cleaning inconsistent features...")
    dep_delay_check = df['dep_delay'] == ((df['dep_time'] - df['sched_dep_time']).dt.total_seconds() / 60)
    df = df[dep_delay_check]

    arr_delay_check = df['arr_delay'] == ((df['arr_time'] - df['sched_arr_time']).dt.total_seconds() / 60)
    df = df[arr_delay_check]
    return df

def drop_duplicates(df):
    logging.info("Dropping duplicates...")
    df.drop_duplicates(inplace=True)
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

    df["daily_flight_count"] = df.groupby(["airline", "date"]).transform("size")

    airline_delay_group = df.groupby(["airline", "date"]).agg({
        "dep_delay": "sum", "arr_delay": "sum", "daily_flight_count": "mean"
    }).reset_index()
    airline_delay_group["airline_daily_performance_kpi"] = (
        (airline_delay_group["dep_delay"] + airline_delay_group["arr_delay"]) / airline_delay_group["daily_flight_count"]
    )
    airline_delay_group.drop(["dep_delay", "arr_delay", "daily_flight_count"], axis=1, inplace=True)
    df = df.merge(airline_delay_group, on=["airline", "date"], how="left")

    airline_total_aircraft_count = df.groupby("airline")["tailnum"].nunique()
    df["aircraft_count_by_airline"] = df["airline"].map(airline_total_aircraft_count)

    bins = [-np.inf, -10.0, -5.0, 0.0, 5.0, np.inf]
    labels = ["Level 1", "Level 2", "Level 3", "Level 4", "Level 5"]
    df["dep_delay_category"] = pd.cut(df["dep_delay"], bins=bins, labels=labels)

    columns_to_be_remove = ["date_string", "hour_check_dep", "hour_check_sched"]
    corrs = ["air_time", "flight", "dewp", "wind_gust", "daily_flight_count"]
    cat_with_high_card = [col for col in df.columns if df[col].nunique() > 80 and str(df[col].dtypes) in ["category", "object"]]
    date_features = df.select_dtypes(include="datetime64").columns.to_list()
    other_features = ["carrier", "origin"]
    cols_will_be_not_used = corrs + cat_with_high_card + date_features + other_features + columns_to_be_remove

    feature_columns = [col for col in df.columns if col not in cols_will_be_not_used]
    df = df[feature_columns]

    df["distance_category"] = df["distance_category"].cat.codes
    df["dep_delay_category"] = df["dep_delay_category"].cat.codes

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

    train_df.to_csv(os.path.join(output_dir, "train.csv"), index=False)
    val_df.to_csv(os.path.join(output_dir, "validation.csv"), index=False)
    test_df.to_csv(os.path.join(output_dir, "test.csv"), index=False)

    logging.info(f"Train shape: {train_df.shape}")
    logging.info(f"Validation shape: {val_df.shape}")
    logging.info(f"Test shape: {test_df.shape}")
    logging.info("Data saved successfully.")

# ----------------------------------------
# Main
# ----------------------------------------
def main(args):
    df = load_data(args.input_path)
    df = drop_missing_values(df)
    df = clean_time_columns(df)
    df = fill_missing_wind_data(df)
    df = clean_inconsistent_features(df)
    df = drop_duplicates(df)
    df = feature_engineering(df)
    df_train, df_val, df_test = split_data(df)
    save_data(df_train, df_val, df_test, args.output_path)
    

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", type=str, default="/opt/ml/processing/input/data.csv")
    parser.add_argument("--output-path", type=str, default="/opt/ml/processing/output")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
