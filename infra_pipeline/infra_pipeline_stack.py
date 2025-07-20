from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
)
from constructs import Construct
from .data_engineering_stage import DataEngineeringStage

class InfraPipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Context'ten parametreleri al
        project_name = self.node.try_get_context("project_name") or "data-engineering"
        notification_email = self.node.try_get_context("notification_email")
        
        # GitHub connections information
        github_repo = "kanitvural/aws_data_science_data_engineering_mlops_infra"
        github_branch = "dataengineering"
        connection_arn = self.node.try_get_context("githubConnectionArn")
        
        # Source aşaması
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
                "cdk synth",
            ]
        )
        
        # Pipeline'ı oluştur
        pipeline = pipelines_.CodePipeline(
            self,
            "InfraPipeline",
            synth=synth_step,
        )
        
        # DataEngineeringStage'i parametrelerle oluştur
        data_eng_stage = DataEngineeringStage(
            self, 
            "DataEngineeringStage",
            env=self.env,
            project_name=project_name,
            notification_email=notification_email
        )
        
        pipeline.add_stage(data_eng_stage)

















# from aws_cdk import (
#     Stack,
#     pipelines as pipelines_,
#     aws_codepipeline as codepipeline,
#     aws_codepipeline_actions as codepipeline_actions,
# )
# from constructs import Construct
# from infra_pipeline.data_engineering_stage import DataEngineeringStage

# class InfraPipelineStack(Stack):
#     def __init__(self, scope: Construct, construct_id: str, **kwargs):
#         super().__init__(scope, construct_id, **kwargs)

#         # GitHub connections information
#         github_repo = "kanitvural/aws_data_science_data_engineering_mlops_infra"
#         github_branch = "dataengineering"
#         connection_arn = self.node.try_get_context("githubConnectionArn")

#         # Source aşaması
#         source = pipelines_.CodePipelineSource.connection(
#             repo_string=github_repo,
#             branch=github_branch,
#             connection_arn=connection_arn,
#         )
        
#         synth_step = pipelines_.ShellStep(
#             "Synth",
#             input=source,
#             commands=[
#                 "npm install -g aws-cdk",
#                 "pip install -r requirements.txt",
#                 "cdk synth",
#             ]
#         )

#         # Pipeline'ı oluştur
#         pipeline = pipelines_.CodePipeline(
#             self,
#             "InfraPipeline",
#             synth= synth_step,
#         )
        
#         data_eng_stage = DataEngineeringStage(self, "DataEngineeringStage")
#         pipeline.add_stage(data_eng_stage)
