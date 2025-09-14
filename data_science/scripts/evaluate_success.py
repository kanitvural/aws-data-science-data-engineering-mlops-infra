import shutil
import os
import logging
import boto3
import argparse
import sys
import json

BASE_DIR = "/opt/ml/processing"

INPUT_MODEL_DIR = os.path.join(BASE_DIR, "input", "model")
INPUT_EVALUATION_DIR = os.path.join(BASE_DIR, "input", "evaluation")
OUTPUT_MODEL_DIR = os.path.join(BASE_DIR, "output", "model")

AWS_REGION = os.environ.get("AWS_REGION", "eu-central-1")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
OUTPUT_MODEL_S3_DIR = os.environ.get("OUTPUT_MODEL_S3_DIR", "")
RMSE_THRESHOLD = float(os.environ.get("RMSE_THRESHOLD", "9"))
PROJECT_NAME = os.environ.get("PROJECT_NAME", "data-science")

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
)


def load_evaluation_results():
    evaluation_file = os.path.join(INPUT_EVALUATION_DIR, "evaluation.json")

    if not os.path.exists(evaluation_file):
        logging.error(f"Evaluation file not found: {evaluation_file}")
        raise FileNotFoundError(f"Evaluation file not found: {evaluation_file}")

    try:
        with open(evaluation_file, "r") as f:
            evaluation_data = json.load(f)

        evaluated_rmse = evaluation_data["regression_metrics"]["rmse"]["value"]
        logging.info(f"📊 Evaluated RMSE loaded from file: {evaluated_rmse}")
        return evaluated_rmse

    except KeyError as e:
        logging.error(f"❌ Key not found in evaluation file: {str(e)}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"❌ Failed to parse evaluation JSON: {str(e)}")
        raise


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-model-dir", type=str, default=INPUT_MODEL_DIR)
    parser.add_argument("--input-evaluation-dir", type=str, default=INPUT_EVALUATION_DIR)
    parser.add_argument("--output-model-dir", type=str, default=OUTPUT_MODEL_DIR)
    parser.add_argument("--sns-topic-arn", type=str, default=SNS_TOPIC_ARN)
    parser.add_argument("--region", type=str, default=AWS_REGION)
    parser.add_argument("--output-model-s3-dir", type=str, default=OUTPUT_MODEL_S3_DIR)
    parser.add_argument("--rmse-threshold", type=float, default=RMSE_THRESHOLD)
    parser.add_argument("--project-name", type=str, default=PROJECT_NAME)
    return parser.parse_known_args()


def copy_model(args):
    if not os.path.exists(args.input_model_dir):
        logging.error(f"Source model directory does not exist: {args.input_model_dir}")
        raise FileNotFoundError(f"Source model directory does not exist: {args.input_model_dir}")

    shutil.copytree(args.input_model_dir, args.output_model_dir, dirs_exist_ok=True)
    logging.info(f"✅ Approved final model saved to {args.output_model_dir}")


def send_mail(args, evaluated_rmse):
    if not args.sns_topic_arn:
        logging.warning("SNS_TOPIC_ARN is not provided. Skipping SNS notification.")
        return

    try:
        sns_client = boto3.client("sns", region_name=args.region)
        final_model_s3_path = os.path.join(args.output_model_s3_dir, "model.tar.gz")

        message = (
            f"✅ Model evaluation completed successfully!\n\n"
            f"📊 Evaluation Results:\n"
            f"• Evaluated RMSE: {evaluated_rmse:.4f}\n"
            f"• RMSE Threshold: {args.rmse_threshold}\n"
            f"• Status: PASSED ✅\n\n"
            f"The model performance is under the threshold of {args.rmse_threshold}, meeting the expected criteria.\n\n"
            f"📁 Model saved to S3 path: {final_model_s3_path}\n\n"
            f"🚀 Please proceed with the next phase of the MLOps workflow as planned."
        )
        subject = "✅ SageMaker Model Evaluation - PASSED"

        logging.info(f"📤 Sending SNS notification to topic: {args.sns_topic_arn}")
        response = sns_client.publish(
            TopicArn=args.sns_topic_arn,
            Message=message,
            Subject=subject,
        )
        logging.info(f"📨 SNS notification sent. MessageId: {response['MessageId']}")
    except Exception as e:
        logging.error(f"❌ Failed to send SNS notification: {str(e)}")
        logging.error(f"   Topic ARN used: {args.sns_topic_arn}")

def store_evaluated_final_model_s3_arn_to_ssm(args):
    
    if not args.output_model_s3_dir:
        logging.warning("OUTPUT_MODEL_S3_DIR is not provided. Skipping SSM parameter storage.")
        return

    ssm_client = boto3.client("ssm", region_name=args.region)
    parameter_name = f"/{args.project_name}/final_evaluated_model_s3_dir"
    final_model_s3_path = os.path.join(args.output_model_s3_dir, "model.tar.gz")
    
    try:
        ssm_client.put_parameter(
            Name=parameter_name,
            Value=final_model_s3_path,
            Type="String",
            Overwrite=True,
        )
        logging.info(f"✅ Stored final evaluated model S3 path to SSM Parameter Store: {parameter_name}")
    except Exception as e:
        logging.error(f"❌ Failed to store parameter in SSM: {str(e)}")
        raise


def main(args):
    try:
        logging.info("🚀 Starting model evaluation success process...")
        evaluated_rmse = load_evaluation_results()
        copy_model(args)
        send_mail(args, evaluated_rmse)
        store_evaluated_final_model_s3_arn_to_ssm(args)
        logging.info("✅ Model evaluation success process completed!")
    except Exception as e:
        logging.error(f"❌ Model evaluation success process failed: {str(e)}")
        raise


if __name__ == "__main__":
    args, _ = parse_args()
    main(args)
