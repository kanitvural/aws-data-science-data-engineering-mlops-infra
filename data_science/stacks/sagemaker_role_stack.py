from aws_cdk import (
    Stack,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class SageMakerRoleStack(Stack):
    def __init__(
        self, 
        scope: Construct, 
        id: str, 
        project_name: str,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

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

        CfnOutput(
            self,
            "SageMakerExecutionRoleArn",
            value=self.sagemaker_execution_role.role_arn,
            description="SageMaker Execution Role ARN",
            export_name=f"{project_name}-sagemaker-execution-role-arn",
        )