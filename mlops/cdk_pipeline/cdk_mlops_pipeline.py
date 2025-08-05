from aws_cdk import (
    Stack,
    pipelines as pipelines_,
)
from constructs import Construct
from .mlops_stage import MLOpsStage


class CDKMLOpsPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "mlops"
        notification_email = self.node.try_get_context("notification_email")

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "mlops"
        connection_arn = self.node.try_get_context("githubConnectionArn")

        source = pipelines_.CodePipelineSource.connection(
            repo_string=github_repo,
            branch=github_branch,
            connection_arn=connection_arn,
        )

        synth_step = pipelines_.ShellStep(
            "Synth",
            input=source,
            commands=[
                "npm install -g aws-cdk",
                "pip install --upgrade pip"
                "pip install -r requirements.txt",
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=mlops",
            ],
        )

        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKMLOpsPipeline",
            synth=synth_step,
        )

        mlops_stage = MLOpsStage(
            self,
            id="MLOpsStage",
            project_name=project_name,
            notification_email=notification_email,
        )

        pipeline.add_stage(mlops_stage)
