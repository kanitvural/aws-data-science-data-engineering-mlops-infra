import argparse
import os
import sys
import json
import traceback
import pandas as pd
import xgboost as xgb
import logging

TRAIN_CHANNEL = os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train')
VALIDATION_CHANNEL= os.environ.get('SM_CHANNEL_VALIDATION', '/opt/ml/input/data/validation')
COMBINED_CHANNEL = os.environ.get('SM_CHANNEL_COMBINED', '/opt/ml/input/data/combined')
TEST_CHANNEL = os.environ.get('SM_CHANNEL_TEST', '/opt/ml/input/data/test')
MODEL_DIR = os.environ.get('SM_MODEL_DIR', '/opt/ml/model')
FAILURE_DIR = os.environ.get('SM_FAILURE_DIR', '/opt/ml/failure')
CONFIG_DIR = os.environ.get('SM_CONFIG_DIR', '/opt/ml/input/config')
OUTPUT_DIR = os.environ.get('SM_OUTPUT_DATA_DIR', '/opt/ml/output')

HYPERPARAMS_PATH = os.path.join(CONFIG_DIR, 'hyperparameters.json')
TRAIN_PATH = os.path.join(TRAIN_CHANNEL, 'train.csv')
VALIDATION_PATH = os.path.join(VALIDATION_CHANNEL, 'validation.csv')
COMBINED_PATH = os.path.join(COMBINED_CHANNEL, 'combined.csv')
TEST_PATH = os.path.join(TEST_CHANNEL, 'test.csv')
MODEL_PATH = os.path.join(MODEL_DIR, 'xgboost-model.json')
FAILURE_PATH = os.path.join(FAILURE_DIR, 'failure')


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def load_hyperparameters(path):
    """JSON'dan hiperparametre yükle, string değerleri dönüştür."""
    logging.info(f"Loading hyperparameters from: {path}")
    
    with open(path, 'r') as f:
        params = json.load(f)
    
    # Sadece string değerleri dönüştür
    for k, v in params.items():
        if isinstance(v, str):
            # Bool check
            if v.lower() in ['true', 'false']:
                params[k] = v.lower() == 'true'
            # Number check  
            elif v.replace('.', '').replace('-', '').isdigit():
                params[k] = int(v) if '.' not in v else float(v)
    
    if "learning_rate" in params:
        params["eta"] = params.pop("learning_rate")
    
    params.setdefault("objective", "reg:squarederror")
    params.setdefault("eval_metric", "rmse")

    logging.info(f"Loaded: {params}")
    return params


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--train-path", type=str, default=TRAIN_PATH)
    parser.add_argument("--validation-path", type=str, default=VALIDATION_PATH)
    parser.add_argument("--combined-path", type=str, default=COMBINED_PATH)
    parser.add_argument("--test-path", type=str, default=TEST_PATH)
    parser.add_argument("--model-path", type=str, default=MODEL_PATH)
    parser.add_argument("--hyperparameters-path", type=str, default=HYPERPARAMS_PATH)
    parser.add_argument("--failure-path", type=str, default=FAILURE_PATH)

    return parser.parse_known_args()

def train(args):
    try:
        logging.info("Starting training process...")

        # Load hyperparameters
        if not os.path.exists(args.hyperparameters_path):
            logging.error(f"Hyperparameters file not found at: {args.hyperparameters_path}")
            sys.exit(1)
        params = load_hyperparameters(args.hyperparameters_path)
        num_rounds = int(params.pop("num_round", 250))
        
        # Load train and validation datasets
        
        if args.combined_path and os.path.exists(args.combined_path):
            logging.info(f"Loading combined data from {args.combined_path}")
            train_df = pd.read_csv(args.combined_path)
        else:
            logging.info(f"Loading training data from {args.train_path}")
            train_df = pd.read_csv(args.train_path)
            
        
        if args.test_path and os.path.exists(args.test_path):
            logging.info(f"Loading test data from {args.test_path}")
            val_df = pd.read_csv(args.test_path)
        else:
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
        model = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=num_rounds,
            evals=[(dtrain, "train"), (dval, "validation")],
        )
        logging.info("Training completed.")

        # Save the model
        logging.info(f"Saving model to {args.model_path}")
        
        model.save_model(args.model_path)
        logging.info("Model saved.")
        
    except Exception as e:
        
        trace = traceback.format_exc()
        logging.error(f"Training failed: {e}")
        logging.error(trace)
        try:
            with open(args.failure_path, 'w') as f:
                f.write(f"Training failed:\n{str(e)}\n{trace}")
        except Exception as write_err:
            logging.error(f"Failed to write failure log: {write_err}")
        sys.exit(255)
        
    

if __name__ == "__main__":
    logging.info(f"sys.argv: {sys.argv}")
    args, _ = parse_args()
    train(args)
