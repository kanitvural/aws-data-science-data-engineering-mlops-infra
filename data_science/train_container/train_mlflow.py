# requirements.txt
# mlflow
# requests_auth_aws_sigv4

import argparse
import os
import sys
import json
import traceback
import pandas as pd
import xgboost as xgb
import logging

# MLflow - opsiyonel import
try:
    import mlflow
    import mlflow.xgboost
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

TRAIN_CHANNEL = os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
VALIDATION_CHANNEL = os.environ.get("SM_CHANNEL_VALIDATION", "/opt/ml/input/data/validation")
MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
FAILURE_DIR = os.environ.get("SM_FAILURE_DIR", "/opt/ml/failure")
CONFIG_DIR = os.environ.get("SM_CONFIG_DIR", "/opt/ml/input/config")
OUTPUT_DIR = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output")

HYPERPARAMS_PATH = os.path.join(CONFIG_DIR, "hyperparameters.json")
TRAIN_PATH = os.path.join(TRAIN_CHANNEL, "train.csv")
VALIDATION_PATH = os.path.join(VALIDATION_CHANNEL, "validation.csv")
MODEL_PATH = os.path.join(MODEL_DIR, "xgboost-model.json")
FAILURE_PATH = os.path.join(FAILURE_DIR, "failure")

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)

def load_hyperparameters(path):
    """JSON'dan hiperparametre yükle, string değerleri dönüştür."""
    logging.info(f"Loading hyperparameters from: {path}")

    with open(path, "r") as f:
        params = json.load(f)

    # Sadece string değerleri dönüştür
    for k, v in params.items():
        if isinstance(v, str):
            # Bool check
            if v.lower() in ["true", "false"]:
                params[k] = v.lower() == "true"
            # Number check
            elif v.replace(".", "").replace("-", "").isdigit():
                params[k] = int(v) if "." not in v else float(v)

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
    parser.add_argument("--model-path", type=str, default=MODEL_PATH)
    parser.add_argument("--hyperparameters-path", type=str, default=HYPERPARAMS_PATH)
    parser.add_argument("--failure-path", type=str, default=FAILURE_PATH)
    return parser.parse_known_args()

def train(args):
    try:
        logging.info("Starting training process...")

        # MLflow setup - environment variable'ları kontrol et
        mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI")
        #mlflow_arn = os.environ.get("MLFLOW_TRACKING_ARN") 
        mlflow_experiment = os.environ.get("MLFLOW_EXPERIMENT_NAME", "sagemaker-xgboost")
        mlflow_run_name = os.environ.get("MLFLOW_RUN_NAME")
        
        if MLFLOW_AVAILABLE and mlflow_uri:# and mlflow_arn:
            #os.environ["MLFLOW_TRACKING_AWS_SIGV4"] = "true" 
            
            mlflow.set_tracking_uri(mlflow_uri)
            mlflow.set_experiment(mlflow_experiment)
            mlflow.start_run(run_name=mlflow_run_name)
            logging.info(f"MLflow enabled: {mlflow_uri}, experiment: {mlflow_experiment}")
        else:
            logging.info("MLflow disabled - missing URI or ARN")

        # Load hyperparameters
        if not os.path.exists(args.hyperparameters_path):
            logging.error(f"Hyperparameters file not found at: {args.hyperparameters_path}")
            sys.exit(1)

        params = load_hyperparameters(args.hyperparameters_path)
        num_rounds = int(params.pop("num_round", 250))

        # MLflow log params
        if MLFLOW_AVAILABLE and mlflow.active_run():
            mlflow.log_params(params)
            mlflow.log_param("num_rounds", num_rounds)

        # Load training dataset
        if not os.path.exists(args.train_path):
            logging.error(f"Training data file not found at: {args.train_path}")
            sys.exit(1)

        logging.info(f"Loading training data from {args.train_path}")
        train_df = pd.read_csv(args.train_path)

        # Separate features and labels
        target = "dep_delay"
        X_train = train_df.drop(columns=[target])
        X_train = X_train.astype({col: "float64" for col in X_train.select_dtypes(include="int").columns})

        y_train = train_df[target]

        # Convert to DMatrix
        dtrain = xgb.DMatrix(data=X_train, label=y_train)

        # Check if validation data exists
        has_validation = os.path.exists(args.validation_path)
        evals_list = [(dtrain, "train")]

        if has_validation:
            logging.info(f"Loading validation data from {args.validation_path}")
            val_df = pd.read_csv(args.validation_path)

            X_val = val_df.drop(columns=[target])
            X_val = X_val.astype({col: "float64" for col in X_val.select_dtypes(include="int").columns})
            y_val = val_df[target]
            dval = xgb.DMatrix(data=X_val, label=y_val)

            evals_list.append((dval, "validation"))
            logging.info("Training with separate validation set (hyperparameter tuning mode)")
        else:
            logging.info("No validation data found. Training with combined dataset (final training mode)")

        # Train the model
        logging.info("Starting training...")

        evals_result = {}
        model = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=num_rounds,
            evals=evals_list,
            evals_result=evals_result,
            verbose_eval=50 if has_validation else False,
            early_stopping_rounds=10,
        )
        
        if has_validation:
            train_rmse = evals_result['train']['rmse'][model.best_iteration]
            val_rmse = evals_result['validation']['rmse'][model.best_iteration]
            logging.info("Best iteration results")
            logging.info(f"train-rmse={train_rmse} | validation-rmse={val_rmse}")
            
            # MLflow log metrics
            if MLFLOW_AVAILABLE and mlflow.active_run():
                mlflow.log_metric("train_rmse", train_rmse)
                mlflow.log_metric("validation_rmse", val_rmse)
        else:
            logging.info("Best iteration result")
            train_rmse = evals_result['train']['rmse'][-1]
            logging.info(f"train-rmse={train_rmse}")
            
            # MLflow log metrics
            if MLFLOW_AVAILABLE and mlflow.active_run():
                mlflow.log_metric("train_rmse", train_rmse)
        
        logging.info("Training completed.")

     
        logging.info(f"Saving model to {args.model_path}")
        model.save_model(args.model_path)
  
        if MLFLOW_AVAILABLE and mlflow.active_run():
            # run_id = mlflow.active_run().info.run_id
            # model_uri = f"runs:/{run_id}/model"

            input_example = X_train.head(5) if len(X_train) > 0 else None

            mlflow.xgboost.log_model(
                model, 
                name="model", 
                input_example=input_example,  
                model_format="json"  
            )

            logging.info("Model logged.")

            # registered_model_name = "XGBoostModel"
            # mlflow.register_model(model_uri, registered_model_name)
            # logging.info(f"Model registered in MLflow Model Registry as {registered_model_name}")

        # Save feature importance for analysis
        importance_path = os.path.join(MODEL_DIR, "feature_importance.json")
        feature_importance = model.get_score(importance_type="weight")
        with open(importance_path, "w") as f:
            json.dump(feature_importance, f, indent=2)
        logging.info(f"Feature importance saved to {importance_path}")

        # MLflow end run
        if MLFLOW_AVAILABLE and mlflow.active_run():
            mlflow.end_run()

    except Exception as e:
        trace = traceback.format_exc()
        logging.error(f"Training failed: {e}")
        logging.error(trace)
        
        # MLflow end run on error
        if MLFLOW_AVAILABLE and mlflow.active_run():
            mlflow.end_run(status="FAILED")
            
        try:
            with open(args.failure_path, "w") as f:
                f.write(f"Training failed:\n{str(e)}\n{trace}")
        except Exception as write_err:
            logging.error(f"Failed to write failure log: {write_err}")
        sys.exit(255)

if __name__ == "__main__":
    logging.info(f"sys.argv: {sys.argv}")
    args, _ = parse_args()
    train(args)
