from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_iam as iam,
    aws_lambda as lambda_,
    RemovalPolicy,
    CfnOutput,
    Duration,
    Fn,
)
from constructs import Construct

from aws_cdk.aws_s3_notifications import LambdaDestination


class S3LambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)


        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")


        # ----------------------------------------------------------------------
        # S3 Bucket
        # ----------------------------------------------------------------------
        bucket = s3.Bucket(
            self,
            id="MLOpsBucket",
            bucket_name=f"{project_name}-bucket-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Bucket Policy: shap-analysis/report.pdf herkes erişebilsin
        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AnyPrincipal()],
                actions=["s3:GetObject"],
                resources=[f"{bucket.bucket_arn}/shap-analysis/report.pdf"],
            )
        )

        CfnOutput(
            self,
            "S3BucketName",
            value=bucket.bucket_name,
            description="S3 Bucket name for MLOps data",
            export_name="MLOpsBucketName",
        )

        # ----------------------------------------------------------------------
        # Lambda Roles
        # ----------------------------------------------------------------------
        shap_lambda_role = iam.Role(
            self,
            f"{project_name}-shap-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        shap_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "sns:Publish",
                ],
                resources=["*"],
            )
        )

        monitoring_lambda_role = iam.Role(
            self,
            f"{project_name}-monitoring-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        monitoring_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "sns:Publish",
                ],
                resources=["*"],
            )
        )

        # ----------------------------------------------------------------------
        # Lambda Functions
        # ----------------------------------------------------------------------
        shap_lambda = lambda_.Function(
            self,
            f"{project_name}-shap-lambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/shap_report"),
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "REGION": self.region,
                "SNS_TOPIC_ARN": sns_topic_arn,
            },
            role=shap_lambda_role,
            timeout=Duration.minutes(5),
        )

        monitoring_lambda = lambda_.Function(
            self,
            f"{project_name}-monitoring-lambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/model_monitor"),
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "REGION": self.region,
                "SNS_TOPIC_ARN": sns_topic_arn,
            },
            role=monitoring_lambda_role,
            timeout=Duration.minutes(5),
        )

        # ----------------------------------------------------------------------
        # Event Notifications
        # ----------------------------------------------------------------------
        # shap lambda: shap-analysis/ yolundaki .pdf dosyalarını tetikleyip çalışacak
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            LambdaDestination(shap_lambda),
            s3.NotificationKeyFilter(prefix="shap-analysis/", suffix=".pdf")
        )

        # monitoring lambda: monitoring-results/ yolundaki .json dosyalarını tetikleyip çalışacak
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            LambdaDestination(monitoring_lambda),
            s3.NotificationKeyFilter(prefix="monitoring-results/", suffix=".json")
        )

        # ----------------------------------------------------------------------
        # CFN Outputs
        # ----------------------------------------------------------------------
        CfnOutput(
            self,
            "ShapLambdaArn",
            value=shap_lambda.function_arn,
        )
        CfnOutput(
            self,
            "MonitoringLambdaArn",
            value=monitoring_lambda.function_arn,
        )
