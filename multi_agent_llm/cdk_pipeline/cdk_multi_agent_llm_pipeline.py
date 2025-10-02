from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_ssm as ssm,
    Fn,
)
from constructs import Construct
from .multi_agent_llm_stage import MultiAgentLLMStage


class CDKLLMPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "multi-agent-llm"
        pipeline_name = f"{project_name}-pipeline-{self.account}"


        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "llm"
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
                "pip install --upgrade pip",
                "pip install -r requirements.txt",
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=llm",
            ],
        )

        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKMultiAgentLLMPipeline",
            pipeline_name=pipeline_name,
            synth=synth_step,
        )

        multi_agent_llm_infra_stage = MultiAgentLLMStage(
            self,
            id="MultiAgentLLMInfraStage",
            project_name=project_name,
        )

        pipeline.add_stage(multi_agent_llm_infra_stage)
      
