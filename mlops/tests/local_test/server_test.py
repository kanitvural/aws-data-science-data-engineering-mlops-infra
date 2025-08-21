import requests
import pandas as pd
import logging

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

base_url = "http://localhost:8080"
headers = {"Content-type": "text/csv"}
csv_file = "test.csv"

def predict(payload, headers):
    response = requests.post(f"{base_url}/invocations", data=payload, headers=headers)
    logger.info(f"Prediction Response: {response.text.strip()}")

def main():
    df = pd.read_csv(csv_file, header=None)
    sample_rows = df.sample(n=20, random_state=42).values.tolist()

    for idx, row in enumerate(sample_rows, 1):
        payload = ",".join(map(str, row))
        logger.info(f"Test {idx} | Input: {payload}")
        predict(payload, headers)

if __name__ == "__main__":
    main()
