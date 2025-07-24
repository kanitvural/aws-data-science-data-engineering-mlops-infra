import argparse
import os
import sys
import json
import pandas as pd
import xgboost as xgb
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def load_hyperparameters(path):
    logging.info(f"Loading hyperparameters from: {path}")
    with open(path, 'r') as f:
        params = json.load(f)
    params = {k: float(v) if '.' in str(v) else int(v) if str(v).isdigit() else v for k, v in params.items()}
    logging.info(f"Loaded hyperparameters: {params}")
    return params

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--train-path", type=str, default="/opt/ml/processing/train/train.csv")
    parser.add_argument("--validation-path", type=str, default="/opt/ml/processing/validation/validation.csv")
    parser.add_argument("--model-dir", type=str, default="/opt/ml/model")
    parser.add_argument("--hyperparameters-path", type=str, default="/opt/ml/input/config/hyperparameters.json")

    return parser.parse_args()

def main():
    args = parse_args()

    # Load hyperparameters
    if not os.path.exists(args.hyperparameters_path):
        logging.error(f"Hyperparameters file not found at: {args.hyperparameters_path}")
        sys.exit(1)
    params = load_hyperparameters(args.hyperparameters_path)
    num_rounds = int(params.pop("n_estimators", 250))
    
    # Load train and validation datasets
    
    if not os.path.exists(args.train_path):
        logging.error(f"Training data file not found at: {args.train_path}")
        sys.exit(1)
    
    if not os.path.exists(args.validation_path):
        logging.error(f"Validation data file not found at: {args.validation_path}")
        sys.exit(1)
    
    logging.info(f"Loading training data from {args.train_path}")
    train_df = pd.read_csv(args.train_path)
    
    logging.info(f"Loading validation data from {args.validation_path}")
    val_df = pd.read_csv(args.validation_path)
    

    # Separate features and labels
    target ="dep_delay"
    X_train = train_df.drop(columns=[target])
    y_train = train_df[target]

    X_val = val_df.drop(columns=[target])
    y_val = val_df[target]

    # Convert to DMatrix
    dtrain = xgb.DMatrix(data=X_train, label=y_train)
    dval = xgb.DMatrix(data=X_val, label=y_val)

    # Train the model
    logging.info("Starting training...")
    bst = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=num_rounds,
        evals=[(dtrain, "train"), (dval, "validation")],
    )
    logging.info("Training completed.")

    # Save the model
    model_path = os.path.join(args.model_dir, "xgboost-model.json")
    logging.info(f"Saving model to {model_path}")
    
    bst.save_model(model_path)
    logging.info("Model saved.")

if __name__ == "__main__":
    main()
