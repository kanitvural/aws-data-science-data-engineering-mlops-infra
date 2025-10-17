# stacks/s3_stack.py       
from aws_cdk import (
    Duration,
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct


class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Data Lake Bucket
        self.data_bucket = s3.Bucket(
            self, 
            id="DataLakeBucket",
            bucket_name=f"{project_name}-data-lake-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="raw-data-lifecycle",
                    prefix="raw/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]
        )
        
            
        # Upload data to S3
        try:
            s3_deployment.BucketDeployment(
                self,
                id="DeployData",
                sources=[s3_deployment.Source.asset("data_engineering/data")],
                destination_bucket=self.data_bucket,
                destination_key_prefix="data/"
            )
        except Exception as e:
            print(f"Warning: Could not deploy scripts: {e}")
            
            
        try: 
            # Artifacts Bucket (for Glue scripts, etc.)
            self.artifacts_bucket = s3.Bucket(
                self,
                id="ArtifactsBucket",
                bucket_name=f"{project_name}-artifacts-{self.account}",
                versioned=True,
                encryption=s3.BucketEncryption.S3_MANAGED,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True
            )
        except Exception as e:
            print(f"Warning: Could not create artifacts bucket: {e}")

        # Outputs
        CfnOutput(
            self,
            id="DataLakeBucketName",
            value=self.data_bucket.bucket_name,
            description="Data Lake S3 Bucket Name",
            export_name=f"{project_name}-data-lake-bucket-name"
        )

        CfnOutput(
            self,
            id="DataLakeBucketArn",
            value=self.data_bucket.bucket_arn,
            description="Data Lake S3 Bucket ARN",
            export_name=f"{project_name}-data-lake-bucket-arn"
        )

        CfnOutput(
            self,
            id="ArtifactsBucketName", 
            value=self.artifacts_bucket.bucket_name,
            description="Artifacts S3 Bucket Name",
            export_name=f"{project_name}-artifacts-bucket-name"
        )
        
        CfnOutput(
            self,
            id="ArtifactsBucketArn",
            value=self.artifacts_bucket.bucket_arn,
            description="Artifacts S3 Bucket ARN",
            export_name=f"{project_name}-artifacts-bucket-arn"
        )
        