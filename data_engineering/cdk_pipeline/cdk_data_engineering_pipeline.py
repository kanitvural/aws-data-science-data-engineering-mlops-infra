from aws_cdk import (
    Stack,
    pipelines as pipelines_,
)
from constructs import Construct
from .data_engineering_stage import DataEngineeringStage
from .ec2_stage import EC2Stage


class CDKDataEngineeringPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "data-engineering"
        pipeline_name = f"{project_name}-pipeline-{self.account}"
        notification_email = self.node.try_get_context("notification_email")

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "dataengineering"
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
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=de",
            ],
        )

        # Create the CodePipeline
        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKDataEngineeringPipeline",
            pipeline_name=pipeline_name,
            synth=synth_step,
        )

        # Add the DataEngineeringStage to the pipeline
        data_eng_stage = DataEngineeringStage(
            self,
            id="DataEngineeringStage",
            project_name=project_name,
            notification_email=notification_email,
        )

        # 1️⃣ Infra stage
        data_engineering_infra_deploy = pipeline.add_stage(data_eng_stage)
        

        # 2️⃣ Manual Approval EC2 Step
        
        ec2_stage = EC2Stage(
            self,
            id="DataSimulatorEC2StageDE",
            project_name=project_name,
        )

        manual_approval = pipelines_.ManualApprovalStep(
            id="ManualApprovalBeforeEC2", comment="✅ Please approve this deployment before EC2 stage starts."
        )

        ec2_deploy = pipeline.add_stage(
            stage=ec2_stage,
            pre=[manual_approval],
        )
