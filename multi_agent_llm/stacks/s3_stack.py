# stacks/s3_stack.py       
from aws_cdk import (
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

        self.data_bucket = s3.Bucket(
            self, 
            id="MultiAgentLLMBucket",
            bucket_name=f"{project_name}-bucket-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
          
        # Upload data to S3
        try:
            s3_deployment.BucketDeployment(
                self,
                id="DeployData",
                sources=[s3_deployment.Source.asset("multi_agent_llm/data")],
                destination_bucket=self.data_bucket,
            )
        except Exception as e:
            print(f"Warning: Could not deploy scripts: {e}")
            
            
 
        # Outputs
        CfnOutput(
            self,
            id="MultiAgentLLMBucketName",
            value=self.data_bucket.bucket_name,
            description="Data Lake S3 Bucket Name",
            export_name=f"{project_name}-bucket"
        )
