from aws_cdk import (
    Stack,
    aws_ecr as ecr,
    RemovalPolicy,
)
from constructs import Construct


class ECRStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, project_name: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.data_science_repo = ecr.Repository(
            self,
            "DataScienceRepo",
            repository_name=f"{project_name}-repository-{self.account}",
            image_scan_on_push=False,
            removal_policy=RemovalPolicy.DESTROY
        )
