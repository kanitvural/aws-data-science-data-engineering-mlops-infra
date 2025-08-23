from aws_cdk import (
    Stack,
    aws_sagemaker as sagemaker,
    aws_iam as iam,
    CfnOutput,
    Fn
)
from constructs import Construct


class SMDevEndpointStack(Stack):

    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        ecr_repository_arn = f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest"
   

        # Import SageMaker execution role
        self.sagemaker_execution_role = iam.Role.from_role_arn(
            self,
            "ImportedSageMakerExecutionRole",
            role_arn=Fn.import_value(f"{project_name}-sagemaker-execution-role-arn"),
            mutable=False
        )
        

        # Model Definition
        model = sagemaker.CfnModel(
            self, "DevModel",
            execution_role_arn=self.sagemaker_execution_role.role_arn,
            primary_container=sagemaker.CfnModel.ContainerDefinitionProperty(
                image=ecr_repository_arn, 
                model_data_url= "s3://data-science-bucket-058264126563/sagemaker-final-training-output/model/pipelines-7877okymrfhn-FlightsFinalTraining-6KIqJxP2g4/output/model.tar.gz"
            ),
            model_name=f"{project_name}-dev-model"
        )

        # Endpoint Config
        endpoint_config = sagemaker.CfnEndpointConfig(
            self, "DevEndpointConfig",
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    initial_instance_count=1,
                    instance_type="ml.t2.medium",
                    model_name=model.attr_model_name,
                    variant_name="AllTraffic"
                )
            ],
            endpoint_config_name="dev-endpoint-config"
        )

        # Endpoint
        endpoint = sagemaker.CfnEndpoint(
            self, "DevEndpoint",
            endpoint_config_name=endpoint_config.attr_endpoint_config_name,
            endpoint_name=f"{project_name}-dev-endpoint"
        )

        # Useful Outputs
        CfnOutput(
            self, "DevEndpointName",
            value=endpoint.endpoint_name,
            description="SageMaker Dev Endpoint name"
        )
        CfnOutput(
            self, "DevModelName",
            value=model.model_name,
            description="SageMaker Dev Model name"
        )
        CfnOutput(
            self, "DevEndpointConfigName",
            value=endpoint_config.endpoint_config_name,
            description="SageMaker Dev Endpoint Config name"
        )
        
