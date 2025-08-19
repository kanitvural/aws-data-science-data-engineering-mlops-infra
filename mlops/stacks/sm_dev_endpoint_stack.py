from aws_cdk import (
    Stack,
    aws_sagemaker as sagemaker,
    aws_iam as iam,
    CfnOutput,
    Fn
)
from constructs import Construct


class SagemakerDevStack(Stack):

    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        
        ecr_repository_arn = (
            f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest"
        )
        
        data_science_bucket_name = Fn.import_value("DataScienceBucketName")

        # SageMaker execution role
        self.sagemaker_execution_role = iam.Role(
            self,
            "SageMakerExecutionRole",
            role_name=f"SageMakerExecutionRole-{project_name}-{self.account}",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"),
            ],
        )

        # S3 permissions for the specific bucket
        self.sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                resources=["*"],
            )
        )

        # ECR permissions
        self.sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:DescribeRepositories",
                    "ecr:DescribeImages",
                ],
                resources=["*"],
            )
        )

        # SNS permissions
        self.sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sns:Publish",
                    "sns:GetTopicAttributes",
                ],
                resources=["*"],
            )
        )

        # CloudWatch Logs permissions
        self.sagemaker_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=["*"],
            )
        )

        # Model Definition
        model = sagemaker.CfnModel(
            self, "DevModel",
            execution_role_arn=self.sagemaker_execution_role.role_arn,
            primary_container=sagemaker.CfnModel.ContainerDefinitionProperty(
                image=ecr_repository_arn, 
                model_data_url= "s3://data-science-bucket-058264126563/sagemaker-final-training-output/model/pipelines-7877okymrfhn-FlightsFinalTraining-6KIqJxP2g4/output/model.tar.gz"
            ),
            model_name="dev-model"
        )

        # Endpoint Config
        endpoint_config = sagemaker.CfnEndpointConfig(
            self, "DevEndpointConfig",
            production_variants=[
                sagemaker.CfnEndpointConfig.ProductionVariantProperty(
                    initial_instance_count=1,
                    instance_type="ml.t3.large",
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
            endpoint_name="dev-endpoint"
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
        
        CfnOutput(
            self,
            "SageMakerExecutionRoleArn",
            value=self.sagemaker_execution_role.role_arn,
            description="SageMaker Execution Role ARN",
            export_name=f"{project_name}-sagemaker-execution-role-arn",
        )
