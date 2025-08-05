import argparse
import os
import json
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error
import numpy as np
import logging
import sys
import tarfile

BASE_DIR = "/opt/ml/processing"
MODEL_NAME = "xgboost-model.json"
MODEL_TAR_NAME = "model.tar.gz"

MODEL_DIR = os.path.join(BASE_DIR, "model")
MODEL_TAR_PATH = os.path.join(MODEL_DIR, MODEL_TAR_NAME)
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)

TEST_DIR = os.path.join(BASE_DIR, "test")
TEST_PATH = os.path.join(TEST_DIR, "test.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "evaluation")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "evaluation.json")

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR)
    parser.add_argument("--model-dir", type=str, default=MODEL_DIR)
    parser.add_argument("--model-path", type=str, default=MODEL_PATH)
    parser.add_argument("--model-tar-path", type=str, default=MODEL_TAR_PATH)
    parser.add_argument("--test-path", type=str, default=TEST_PATH)
    parser.add_argument("--output-path", type=str, default=OUTPUT_PATH)
    return parser.parse_known_args()


def main(args):

    if not os.path.exists(args.model_tar_path):
        logging.error(f"Model tar file not found: {args.model_tar_path}")
        sys.exit(1)

    logging.info(f"Extracting model from: {args.model_tar_path}")

    with tarfile.open(args.model_tar_path, "r:gz") as tar:
        tar.extractall(path=args.model_dir)

    logging.info(f"Loading model from: {args.model_path}")
    model = xgb.Booster()
    model.load_model(args.model_path)

    logging.info(f"Loading test data from: {args.test_path}")
    df = pd.read_csv(args.test_path)
    target = "dep_delay"
    X_test = df.drop(target, axis=1)
    y_test = df[target]

    dtest = xgb.DMatrix(X_test)
    preds = model.predict(dtest)
    rmse = np.sqrt(mean_squared_error(y_test, preds))

    logging.info(f"RMSE: {rmse}")

    os.makedirs(args.output_dir, exist_ok=True)
    output_data = {
        "regression_metrics": {
            "rmse": {
                "value": rmse,
            }
        }
    }

    with open(args.output_path, "w") as f:
        json.dump(output_data, f)

    logging.info(f"Evaluation saved to: {args.output_path}")


if __name__ == "__main__":
    args, _ = parse_args()
    main(args)
