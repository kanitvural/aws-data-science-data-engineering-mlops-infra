from aws_cdk import (
    Stack,
    aws_s3 as s3,
    RemovalPolicy,
    CfnOutput,
    Duration,
    aws_iam as iam,
    aws_lambda as lambda_,
    Fn
)
from aws_cdk.aws_s3_notifications import LambdaDestination
from constructs import Construct


class S3LambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")
        pipeline_name = f"{project_name}-pipeline-{self.account}"

        # ------------------------
        # S3 Bucket
        # ------------------------
        self.bucket = s3.Bucket(
            self,
            id="DataScienceBucket",
            bucket_name=f"{project_name}-bucket-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,  # Prod'da RETAIN olmalı
            auto_delete_objects=True,
        )

        CfnOutput(
            self,
            "S3BucketName",
            value=self.bucket.bucket_name,
            description="S3 Bucket name for Data Science data",
            export_name="DataScienceBucketName",
        )

        # ------------------------
        # Retrain Lambda Role
        # ------------------------
        retraining_lambda_role = iam.Role(
            self,
            f"{project_name}-retraining-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )

        retraining_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                ],
                resources=[
                    self.bucket.bucket_arn,
                    f"{self.bucket.bucket_arn}/*"
                ],
            )
        )

        retraining_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["sns:Publish"],
                resources=[sns_topic_arn],
            )
        )

        # ------------------------
        # Retrain Lambda Function
        # ------------------------
        retrain_lambda = lambda_.Function(
            self,
            f"{project_name}-retrain-lambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/retrain_model"),
            environment={
                "REGION": self.region,
                "PIPELINE_NAME": pipeline_name,
                "SNS_TOPIC_ARN": sns_topic_arn,
            },
            role=retraining_lambda_role,
            timeout=Duration.minutes(5),
        )

        # ------------------------
        # S3 Event Notification → Lambda
        # ------------------------
        self.bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            LambdaDestination(retrain_lambda),
            s3.NotificationKeyFilter(prefix="retrain_data/", suffix=".csv"),
        )
