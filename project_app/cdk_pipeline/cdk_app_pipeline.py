from aws_cdk import (
    Stack,
    pipelines as pipelines_,
)
from constructs import Construct
from .project_app_stage import ProjectAppPipelineStage


class CDKProjectAppPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "project-app"
        pipeline_name = f"{project_name}-pipeline-{self.account}"
        notification_email = self.node.try_get_context("notification_email")

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "app"
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
                "pip install -r requirements.txt",
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=app",
            ],
        )

        # Create the CodePipeline
        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKProjectAppPipeline",
            pipeline_name=pipeline_name,
            synth=synth_step,
        )

        # Add the ProjectAppPipeline to the pipeline
        project_app_stage = ProjectAppPipelineStage(
            self,
            id="ProjectAppPipelineStage",
            project_name=project_name,
            notification_email=notification_email,
        )

        pipeline.add_stage(project_app_stage)
