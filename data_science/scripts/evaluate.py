import argparse
import os
import json
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error
import numpy as np
import logging
import sys

logging.basicConfig(level=logging.INFO)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, default="/opt/ml/processing/model/xgboost-model.json")
    parser.add_argument("--test-data", type=str, default="/opt/ml/processing/test/test.csv")
    parser.add_argument("--output-path", type=str, default="/opt/ml/processing/evaluation")
    return parser.parse_args()

def main():
    args = parse_args()

    if not os.path.exists(args.model_path):
        logging.error(f"Model file not found at: {args.model_path}")
        sys.exit(1)

    if not os.path.exists(args.test_data):
        logging.error(f"Test data file not found at: {args.test_data}")
        sys.exit(1)

    logging.info(f"Loading test data from: {args.test_data}")
    df = pd.read_csv(args.test_data)
    target = "dep_delay"
    X_test = df.drop(target, axis=1)
    y_test = df[target]

    logging.info(f"Loading model from: {args.model_path}")
    model = xgb.Booster()
    model.load_model(args.model_path)

    dtest = xgb.DMatrix(X_test)
    preds = model.predict(dtest)

    rmse = np.sqrt(mean_squared_error(y_test, preds))
    logging.info(f"Computed RMSE: {rmse}")

    os.makedirs(args.output_path, exist_ok=True)

    output_data = {
        "regression_metrics": {
            "rmse": {
                "value": rmse,
            }
        }
    }

    output_file = os.path.join(args.output_path, "evaluation.json")
    with open(output_file, "w") as f:
        json.dump(output_data, f)

    logging.info(f"Saved evaluation report to: {output_file}")

if __name__ == "__main__":
    main()
