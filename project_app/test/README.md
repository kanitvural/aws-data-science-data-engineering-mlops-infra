## Create and Delete Prod Endpoint For Testing Purpose

```
aws sagemaker describe-endpoint --endpoint-name mlops-prod-endpoint

aws sagemaker list-endpoint-configs
"prod-endpoint-config-mlops"

aws sagemaker list-models
"mlops-prod-model"


 aws sagemaker delete-endpoint --endpoint-name mlops-prod-endpoint --region eu-central-1


aws sagemaker create-endpoint \
    --endpoint-name mlops-prod-endpoint \
    --endpoint-config-name prod-endpoint-config-mlops --region eu-central-1

```