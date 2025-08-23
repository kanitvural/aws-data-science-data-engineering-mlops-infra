import boto3
import time
import os
import sys

def main():
    region = os.environ['REGION']
    endpoint_name = os.environ['ENDPOINT_NAME']
    
    sagemaker = boto3.client('sagemaker', region_name=region)
    
    print(f"Waiting for endpoint {endpoint_name} to be InService...")
    
    max_attempts = 40  # 20 minutes
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = sagemaker.describe_endpoint(EndpointName=endpoint_name)
            status = response['EndpointStatus']
            
            print(f"Endpoint status: {status} (attempt {attempt + 1}/40)")
            
            if status == 'InService':
                print(f"✅ Endpoint {endpoint_name} is InService!")
                return
            elif status in ['Failed', 'OutOfService']:
                print(f"❌ Endpoint {endpoint_name} failed with status: {status}")
                sys.exit(1)
            
            # wait 30 seconds before next check
            time.sleep(30)
            attempt += 1
            
        except Exception as e:
            if "does not exist" in str(e).lower():
                print(f"Endpoint {endpoint_name} not found yet, waiting...")
                time.sleep(30)
                attempt += 1
                continue
            else:
                print(f"Error: {str(e)}")
                sys.exit(1)
    
    print(f"❌ Timeout: Endpoint {endpoint_name} did not become InService within 20 minutes")
    sys.exit(1)

if __name__ == "__main__":
    main()