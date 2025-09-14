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


class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

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

        CfnOutput(
            self,
            "S3BucketName",
            value=bucket.bucket_name,
            description="S3 Bucket name for MLOps data",
            export_name="MLOpsBucketName",
        )
