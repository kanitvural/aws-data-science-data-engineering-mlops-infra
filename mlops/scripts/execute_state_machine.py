#!/usr/bin/env python3

import boto3
import sys
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def find_step_function_arn(client, target_substring):
    """Find Step Function ARN by project name"""
    response = client.list_state_machines()
    
    for state_machine in response['stateMachines']:
        if target_substring in state_machine['name']:
            logger.info(f"Step Function found: {state_machine['name']}")
            return state_machine['stateMachineArn']
    
    logger.error(f"Step Function not found: {target_substring}")
    return None


def start_execution(client, arn, project_name):
    """Start Step Function execution"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    execution_name = f"{project_name}-dev-test-{timestamp}"
    
    logger.info(f"Execution initializing: {execution_name}")
    
    response = client.start_execution(
        stateMachineArn=arn,
        name=execution_name,
        input="{}"
    )
    
    logger.info(f"Execution started successfully: {response['executionArn']}")


def main():
    
    region = os.environ.get('REGION', 'eu-central-1')
    step_func_name_substring = os.environ.get('STEP_FUNCTION_NAME_SUBSTRING', 'DevEndpointEvaluationWorkflow')
    project_name = os.environ.get('PROJECT_NAME', 'mlops')

    
    try:
        client = boto3.client('stepfunctions', region_name=region)
        
        # Find Step Function
        arn = find_step_function_arn(client, step_func_name_substring)
        if not arn:
            sys.exit(1)
        
        # Start execution
        start_execution(client, arn, project_name)
        logger.info("Step Function triggered successfully!")
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()