from aws_cdk import (
    Stack,
    aws_sagemaker as sagemaker,
    aws_iam as iam,
    aws_applicationautoscaling as autoscaling,
    aws_cloudwatch as cloudwatch,
    aws_ssm as ssm,
    CfnOutput,
    Duration,
    Fn,
)
from constructs import Construct


class SMProdEndpointStack(Stack):

    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs) -> None:
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
            self,
            "LatestModelPackageArn",
            parameter_name=parameter_name
        ).string_value

        # Production Model - Model Registry ARN will be placed here
        model = sagemaker.CfnModel(
            self,
            "ProdModel",
            execution_role_arn=self.sagemaker_execution_role.role_arn,
            containers=[
                sagemaker.CfnModel.ContainerDefinitionProperty(
                    model_package_name= latest_model_package_arn
                )
            ],
            model_name=f"{project_name}-prod-model",
        )

        # Endpoint Config - Autoscaling
        endpoint_config = sagemaker.CfnEndpointConfig(
            self,
            "ProdEndpointConfig",
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    initial_instance_count=1,
                    instance_type="ml.t2.large",
                    model_name=model.attr_model_name,
                    variant_name="AllTraffic",
                )
            ],
            endpoint_config_name=f"prod-endpoint-config-{project_name}",
        )

        # Endpoint
        endpoint = sagemaker.CfnEndpoint(
            self,
            "ProdEndpoint",
            endpoint_config_name=endpoint_config.attr_endpoint_config_name,
            endpoint_name=f"{project_name}-prod-endpoint",
        )

        # Auto Scaling
        scaling_target = autoscaling.ScalableTarget(
            self,
            "EndpointScalingTarget",
            service_namespace=autoscaling.ServiceNamespace.SAGEMAKER,
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            resource_id=f"endpoint/{endpoint.endpoint_name}/variant/AllTraffic",
            min_capacity=1,
            max_capacity=5,
        )

        # CPU scaling

        scaling_target.scale_on_metric(
            "CPUScaling",
            metric=cloudwatch.Metric(
                metric_name="CPUUtilization",
                namespace="AWS/SageMaker",
                dimensions_map={"EndpointName": endpoint.endpoint_name, "VariantName": "AllTraffic"},
                statistic="Average",
                period=Duration.minutes(1),
            ),
            scaling_steps=[
                autoscaling.ScalingInterval(lower=70, change=+1),  # CPU >70% scale up
            ],
            adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=Duration.minutes(5),
        )

        # Outputs
        
        CfnOutput(
            self,
            "ProdEndpointName",
            value=endpoint.endpoint_name,
            description="Production Endpoint name",
        )
        
        CfnOutput(
            self, "ProdModelName",
            value=model.model_name,
            description="SageMaker Prod Model name"
        )
        
        CfnOutput(
            self, "ProdEndpointConfigName",
            value=endpoint_config.endpoint_config_name,
            description="SageMaker Prod Endpoint Config name"
        )
