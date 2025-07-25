from aws_cdk import (
    Stack,
    aws_s3 as s3,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

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
            export_name=f"{project_name}-s3-bucket-name",
        )
