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

base_dir = "/opt/ml/processing"
model_name = "xgboost-model.json"
model_tar_name = "model.tar.gz"

model_dir = os.path.join(base_dir, "model")
model_tar_path = os.path.join(model_dir, model_tar_name)
model_path = os.path.join(model_dir, model_name)

test_dir = os.path.join(base_dir, "test")
test_path = os.path.join(test_dir, "test.csv")

output_dir = os.path.join(base_dir, "evaluation")
output_path = os.path.join(output_dir, "evaluation.json")


logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, default=output_dir)
    parser.add_argument("--model-dir", type=str, default=model_dir)
    parser.add_argument("--model-path", type=str, default=model_path)
    parser.add_argument("--model-tar-path", type=str, default=model_tar_path)
    parser.add_argument("--test-path", type=str, default=test_path)
    parser.add_argument("--output-path", type=str, default=output_path)
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
