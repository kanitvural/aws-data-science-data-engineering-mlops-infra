import numpy as np
import pandas as pd
import sys
import os
import logging
import argparse
from sklearn.model_selection import train_test_split


BASE_DIR = "/opt/ml/processing"
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TRAIN_DIR = os.path.join(OUTPUT_DIR, "train")
VALIDATION_DIR = os.path.join(OUTPUT_DIR, "validation")
TEST_DIR = os.path.join(OUTPUT_DIR, "test")
# Combined dataset directory for final training job
COMBINED_DIR = os.path.join(OUTPUT_DIR, "combined")
# Baseline dataset directory for sagemaker model monitoring
BASELINE_DIR = os.path.join(OUTPUT_DIR, "baseline")
# Raw drift test data directory
DRIFT_DIR = os.path.join(OUTPUT_DIR, "drift")


INPUT_PATH = os.path.join(INPUT_DIR, "flights_sample.csv")
TRAIN_PATH = os.path.join(TRAIN_DIR, "train.csv")
VALIDATION_PATH = os.path.join(VALIDATION_DIR, "validation.csv")
TEST_PATH = os.path.join(TEST_DIR, "test.csv")
COMBINED_PATH = os.path.join(COMBINED_DIR, "train.csv")
BASELINE_PATH = os.path.join(BASELINE_DIR, "baseline.csv")
DRIFT_RAW_PATH = os.path.join(DRIFT_DIR, "raw_test_data_for_model_drift.csv")

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR)
    parser.add_argument("--input-path", type=str, default=INPUT_PATH)
    parser.add_argument("--train-path", type=str, default=TRAIN_PATH)
    parser.add_argument("--validation-path", type=str, default=VALIDATION_PATH)
    parser.add_argument("--test-path", type=str, default=TEST_PATH)
    parser.add_argument("--combined-path", type=str, default=COMBINED_PATH)
    parser.add_argument("--baseline-path", type=str, default=BASELINE_PATH)
    parser.add_argument("--drift-raw-path", type=str, default=DRIFT_RAW_PATH)

    return parser.parse_known_args()


def load_data(file_path):
    logging.info(f"Loading dataset from {file_path}")
    if not os.path.exists(file_path):
        logging.error(f"Dataset not found: {file_path}")
        sys.exit(1)
    df = pd.read_csv(file_path, parse_dates=["dep_time", "sched_dep_time", "arr_time", "sched_arr_time", "date"])
    df["date_string"] = df["date_string"].astype(str)
    df["airline"] = df["airline"].str.lower().str.replace(r"\s+", "_", regex=True) .str.replace(r"\.", "", regex=True)   
    logging.info(f"Dataset shape: {df.shape}")
    return df


def create_drift_data(df_original, random_state=42):
    """
    Create raw test data with moderate drift for model monitoring
    """
    logging.info("Creating drift test data...")
    
    np.random.seed(random_state)
    
    # Sample same size as test data would be (approximately 20% of original)
    sample_size = int(len(df_original) * 0.2)
    df_drift = df_original.sample(n=sample_size, random_state=random_state).copy()
    
    # Remove target variable as this is for prediction
    if 'dep_delay' in df_drift.columns:
        df_drift.drop('dep_delay', axis=1, inplace=True)
    
    # 1. Apply airline distribution drift
    airline_multipliers = {
        'united_air_lines_inc': 1.25,
        'alaska_airlines_inc': 0.75,
        'american_airlines_inc': 1.15,
        'delta_air_lines_inc': 0.85,
        'southwest_airlines_co': 1.20,
    }
    
    airline_dfs = []
    for airline in df_drift['airline'].unique():
        airline_df = df_drift[df_drift['airline'] == airline].copy()
        
        if airline in airline_multipliers:
            multiplier = airline_multipliers[airline]
            new_size = int(len(airline_df) * multiplier)
            new_size = max(1, min(new_size, len(airline_df) * 2))
            
            if new_size > len(airline_df):
                additional_samples = new_size - len(airline_df)
                additional_df = airline_df.sample(n=additional_samples, replace=True, random_state=random_state)
                airline_df = pd.concat([airline_df, additional_df], ignore_index=True)
            elif new_size < len(airline_df):
                airline_df = airline_df.sample(n=new_size, random_state=random_state)
        
        airline_dfs.append(airline_df)
    
    df_drift = pd.concat(airline_dfs, ignore_index=True).sample(frac=1, random_state=random_state).reset_index(drop=True)
    
    # 2. Apply weather conditions drift
    temp_shift = np.random.normal(5, 2, len(df_drift))
    df_drift['temp'] = df_drift['temp'] + temp_shift
    
    humid_multiplier = np.random.normal(1.12, 0.03, len(df_drift))
    df_drift['humid'] = np.clip(df_drift['humid'] * humid_multiplier, 0, 100)
    
    wind_multiplier = np.random.normal(1.18, 0.05, len(df_drift))
    df_drift['wind_speed'] = df_drift['wind_speed'] * wind_multiplier
    
    if 'dewp' in df_drift.columns:
        df_drift['dewp'] = df_drift['dewp'] + temp_shift * 0.7
    
    # 3. Apply distance drift
    distance_multiplier = np.random.normal(1.12, 0.08, len(df_drift))
    df_drift['distance'] = df_drift['distance'] * distance_multiplier
    
    if 'air_time' in df_drift.columns:
        df_drift['air_time'] = df_drift['air_time'] * (distance_multiplier ** 0.8)
    
    # 4. Apply temporal drift
    hour_shift_mask = np.random.random(len(df_drift)) < 0.15
    hour_shift = np.random.choice([-2, -1, 1, 2], size=np.sum(hour_shift_mask))
    df_drift.loc[hour_shift_mask, 'hour'] = np.clip(
        df_drift.loc[hour_shift_mask, 'hour'] + hour_shift, 0, 23
    )
    
    if np.any(hour_shift_mask):
        new_minutes = np.random.choice([0, 15, 30, 45], size=np.sum(hour_shift_mask))
        df_drift.loc[hour_shift_mask, 'minute'] = new_minutes
    
    # 5. Apply pressure drift
    pressure_shift = np.random.normal(-2.5, 1.5, len(df_drift))
    df_drift['pressure'] = df_drift['pressure'] + pressure_shift
    
    logging.info(f"Drift data created with shape: {df_drift.shape}")
    return df_drift


def feature_engineering(df):
    logging.info("Starting feature engineering...")

    df["distance_ratio_by_total"] = df.groupby("airline")["distance"].transform("sum") / df["distance"].sum()

    bins = [0, 500, 1000, np.inf]
    labels = ["0-500 miles", "500-1000 miles", "1000+ miles"]
    df["distance_category"] = pd.cut(df["distance"], bins=bins, labels=labels, ordered=True)
    df["distance_category"] = df["distance_category"].cat.codes

    df["daily_flight_count"] = df.groupby(["airline", "date"])["airline"].transform("count")

    airline_total_aircraft_count = df.groupby("airline")["tailnum"].nunique()
    df["aircraft_count_by_airline"] = df["airline"].map(airline_total_aircraft_count)

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


def split_data(df, test_size=0.2, val_size=0.2, random_state=42, shuffle=True):
    logging.info("Splitting data into train, validation, and test sets...")
    df_train_val, df_test = train_test_split(df, test_size=test_size, random_state=random_state, shuffle=shuffle)
    val_ratio = val_size / (1 - test_size)
    df_train, df_val = train_test_split(df_train_val, test_size=val_ratio, random_state=random_state)
    return df_train, df_val, df_test


def save_data(train_df, val_df, test_df, drift_df, args):
    logging.info(f"Saving datasets to {args.output_dir}...")
    os.makedirs(args.output_dir, exist_ok=True)

    dirs = ["train", "validation", "test", "combined", "baseline", "drift"]
    for d in dirs:
        os.makedirs(os.path.join(args.output_dir, d), exist_ok=True)

    train_df.to_csv(args.train_path, index=False)
    val_df.to_csv(args.validation_path, index=False)
    test_df.to_csv(args.test_path, index=False)

    # combined_df for final training job.
    combined_df = pd.concat([train_df, val_df], ignore_index=True)
    combined_df.to_csv(args.combined_path, index=False)

    # baseline_df for sagemaker model monitoring.
    baseline_df = combined_df.copy()
    baseline_df.to_csv(args.baseline_path, index=False)
    
    # drift_df for model drift testing (raw data without target)
    drift_df.to_csv(args.drift_raw_path, index=False)

    logging.info(f"Train shape: {train_df.shape}")
    logging.info(f"Validation shape: {val_df.shape}")
    logging.info(f"Test shape: {test_df.shape}")
    logging.info(f"Combined df for final trainig job shape: {combined_df.shape}")
    logging.info(f"Baseline df for sagemaker model monitoring shape: {baseline_df.shape}")
    logging.info(f"Raw drift test data shape: {drift_df.shape}")
    logging.info("Data saved successfully.")


def main(args):
    # Load and do initial processing
    df_original = load_data(args.input_path)
    
    # Create drift data before feature engineering (using raw processed data)
    df_drift = create_drift_data(df_original)
    
    # Apply feature engineering to original data
    df = feature_engineering(df_original)
    df_train, df_val, df_test = split_data(df)
    
    # Save all datasets including drift data
    save_data(df_train, df_val, df_test, df_drift, args)


if __name__ == "__main__":
    logging.info("Starting preprocessing...")
    args, _ = parse_args()
    main(args)
    logging.info("Preprocessing completed.")