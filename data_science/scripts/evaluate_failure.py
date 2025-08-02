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

AWS_REGION = os.environ.get("AWS_REGION", "eu-central-1")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
RMSE_THRESHOLD = float(os.environ.get("RMSE_THRESHOLD", "9"))

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
    parser.add_argument("--sns-topic-arn", type=str, default=SNS_TOPIC_ARN)
    parser.add_argument("--region", type=str, default=AWS_REGION)
    parser.add_argument("--rmse-threshold", type=float, default=RMSE_THRESHOLD)
    return parser.parse_known_args()


def send_mail(args, evaluated_rmse):
    if not args.sns_topic_arn:
        logging.warning("SNS_TOPIC_ARN is not provided. Skipping SNS notification.")
        return

    try:
        sns_client = boto3.client("sns", region_name=args.region)

        message = (
            f"✅ Model evaluation completed successfully!\n\n"
            f"📊 Evaluation Results:\n"
            f"• Evaluated RMSE: {evaluated_rmse:.4f}\n"
            f"• RMSE Threshold: {args.rmse_threshold}\n"
            f"• Status: FAILED ❌\n\n"
            f"The model performance did NOT meet the threshold of {args.rmse_threshold}, failing to meet the expected criteria.\n\n"
            "Model was NOT saved for deployment.\n"
            "Please review the training pipeline, adjust model parameters, or improve data quality before retrying."
        )
        subject = "❌ SageMaker Model Evaluation - FAILED"

        response = sns_client.publish(
            TopicArn=args.sns_topic_arn,
            Message=message,
            Subject=subject,
        )
        logging.info(f"📨 SNS notification sent. MessageId: {response['MessageId']}")
    except Exception as e:
        logging.error(f"❌ Failed to send SNS notification: {str(e)}")


def main(args):
    try:
        logging.info("🚀 Starting model evaluation success process...")
        evaluated_rmse = load_evaluation_results()
        send_mail(args, evaluated_rmse)
        logging.info("✅ Model evaluation failed process completed!")
    except Exception as e:
        logging.error(f"❌ Model evaluation failed process failed: {str(e)}")
        raise


if __name__ == "__main__":
    args, _ = parse_args()
    main(args)
