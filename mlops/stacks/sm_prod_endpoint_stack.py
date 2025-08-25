from aws_cdk import (
    Stack,
    aws_sagemaker as sagemaker,
    aws_iam as iam,
    aws_ssm as ssm,
    CfnOutput,
    Fn,
)
from constructs import Construct


class SMProdEndpointStack(Stack):

    def __init__(self, scope: Construct, id: str, project_name: str, instance_config: dict, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Import SageMaker execution role
        self.sagemaker_execution_role = iam.Role.from_role_arn(
            self,
            "ImportedSageMakerExecutionRole",
            role_arn=Fn.import_value(f"{project_name}-sagemaker-execution-role-arn"),
            mutable=False,
        )

        # Import ssm model arn parameter
        parameter_name = f"/{project_name}/latest-approved-model-arn"
        latest_model_package_arn = ssm.StringParameter.from_string_parameter_attributes(
            self, "LatestModelPackageArn", parameter_name=parameter_name
        ).string_value

        # Production Model
        model = sagemaker.CfnModel(
            self,
            "ProdModel",
            execution_role_arn=self.sagemaker_execution_role.role_arn,
            containers=[sagemaker.CfnModel.ContainerDefinitionProperty(model_package_name=latest_model_package_arn)],
            model_name=f"{project_name}-prod-model",
        )

        # Endpoint Config
        endpoint_config = sagemaker.CfnEndpointConfig(
            self,
            "ProdEndpointConfig",
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    initial_instance_count=instance_config["instance_count"],
                    instance_type=instance_config["instance_type"],
                    model_name=model.attr_model_name,
                    variant_name="AllTraffic",
                )
            ],
            endpoint_config_name=f"prod-endpoint-config-{project_name}",
        )
        endpoint_config.add_dependency(model)

        # Endpoint
        endpoint = sagemaker.CfnEndpoint(
            self,
            "ProdEndpoint",
            endpoint_config_name=endpoint_config.attr_endpoint_config_name,
            endpoint_name=f"{project_name}-prod-endpoint",
        )
        endpoint.add_dependency(endpoint_config)

        CfnOutput(
            self,
            "ProdEndpointName",
            value=endpoint.endpoint_name,
            description="Production Endpoint name",
            export_name=f"{project_name}-prod-endpoint-name",
        )

        CfnOutput(
            self,
            "ProdModelName",
            value=model.model_name,
            description="SageMaker Prod Model name",
            export_name=f"{project_name}-prod-model-name",
        )

        CfnOutput(
            self,
            "ProdEndpointConfigName",
            value=endpoint_config.endpoint_config_name,
            description="SageMaker Prod Endpoint Config name",
            export_name=f"{project_name}-prod-endpoint-config-name",
        )
