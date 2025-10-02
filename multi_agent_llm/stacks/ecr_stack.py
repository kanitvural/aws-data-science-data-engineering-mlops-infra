from aws_cdk import (
    Stack,
    aws_ecr as ecr,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class ECRStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.ai_engineering_repo = ecr.Repository(
            self,
            id="AIEngineersRepo",
            repository_name=f"{project_name}-repository-{self.account}",
            image_scan_on_push=False,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_images=True,
        )

        CfnOutput(
            self,
            "AIEngineersRepoURI",
            value=self.ai_engineering_repo.repository_uri,
            description="ECR Repository URI for AI Engineering container",
            export_name=f"{project_name}-ecr-repository-uri",
        )
