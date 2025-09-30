#!/bin/bash

# Automatically fetch AWS account ID and region from AWS CLI config

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

check_env_param() {
local env=$1
if [[ -z "$env" ]]; then
echo "❌ Missing environment parameter!"
echo "Usage: make <bootstrap|deploy|destroy> env=<ds|de|mlops|app|llm>"
exit 1
fi
}

bootstrap() {
local env=$1
check_env_param "$env"
echo "🔹 Bootstrapping environment: $env (Account: $ACCOUNT_ID, Region: $REGION)"

if [[ "$env" == "ds" ]]; then
cdk bootstrap 
--context @aws-cdk/core:bootstrapQualifier=ds 
--qualifier ds 
--toolkit-stack-name CDKToolkit-DS 
aws://$ACCOUNT_ID/$REGION

elif [[ "$env" == "de" ]]; then
cdk bootstrap 
--context @aws-cdk/core:bootstrapQualifier=de 
--qualifier de 
--toolkit-stack-name CDKToolkit-DE 
aws://$ACCOUNT_ID/$REGION

elif [[ "$env" == "mlops" ]]; then
cdk bootstrap 
--context @aws-cdk/core:bootstrapQualifier=mlops 
--qualifier mlops 
--toolkit-stack-name CDKToolkit-MLOPS 
aws://$ACCOUNT_ID/$REGION

elif [[ "$env" == "app" ]]; then
cdk bootstrap 
--context @aws-cdk/core:bootstrapQualifier=app 
--qualifier app 
--toolkit-stack-name CDKToolkit-APP 
aws://$ACCOUNT_ID/$REGION

elif [[ "$env" == "llm" ]]; then
cdk bootstrap 
--context @aws-cdk/core:bootstrapQualifier=llm 
--qualifier llm 
--toolkit-stack-name CDKToolkit-LLM 
aws://$ACCOUNT_ID/$REGION

else
echo "❌ Invalid environment! Use: ds, de, mlops, app, or llm"
exit 1
fi
}

deploy() {
local env=$1
check_env_param "$env"
echo "🚀 Deploying environment: $env (Account: $ACCOUNT_ID, Region: $REGION)"

if [[ "$env" == "ds" ]]; then
cdk deploy 
--context @aws-cdk/core:bootstrapQualifier=ds 
--require-approval never

elif [[ "$env" == "de" ]]; then
cdk deploy CDKDataEngineeringPipelineStack 
--context @aws-cdk/core:bootstrapQualifier=de 
--require-approval never

elif [[ "$env" == "mlops" ]]; then
cdk deploy CDKMLOpsPipelineStack 
--context @aws-cdk/core:bootstrapQualifier=mlops 
--require-approval never

elif [[ "$env" == "app" ]]; then
cdk deploy CDKAppPipelineStack 
--context @aws-cdk/core:bootstrapQualifier=app 
--require-approval never

elif [[ "$env" == "llm" ]]; then
cdk deploy CDKLLMPipelineStack 
--context @aws-cdk/core:bootstrapQualifier=llm 
--require-approval never

else
echo "❌ Invalid environment! Use: ds, de, mlops, app, or llm"
exit 1
fi
}

destroy() {
local env=$1
check_env_param "$env"
echo "⚠️ Destroying environment: $env (Account: $ACCOUNT_ID, Region: $REGION)"

if [[ "$env" == "ds" ]]; then
cdk destroy 
--context @aws-cdk/core:bootstrapQualifier=ds 
--force

elif [[ "$env" == "de" ]]; then
cdk destroy 
--context @aws-cdk/core:bootstrapQualifier=de 
--force

elif [[ "$env" == "mlops" ]]; then
cdk destroy 
--context @aws-cdk/core:bootstrapQualifier=mlops 
--force

elif [[ "$env" == "app" ]]; then
cdk destroy 
--context @aws-cdk/core:bootstrapQualifier=app 
--force

elif [[ "$env" == "llm" ]]; then
cdk destroy 
--context @aws-cdk/core:bootstrapQualifier=llm 
--force

else
echo "❌ Invalid environment! Use: ds, de, mlops, app, or llm"
exit 1
fi
}

# --- Dispatcher ---

action=$1
env=$2

if [[ "$action" == "bootstrap" ]]; then
bootstrap "$env"
elif [[ "$action" == "deploy" ]]; then
deploy "$env"
elif [[ "$action" == "destroy" ]]; then
destroy "$env"
else
echo "❌ Invalid action! Use: bootstrap, deploy, or destroy"
exit 1
fi
