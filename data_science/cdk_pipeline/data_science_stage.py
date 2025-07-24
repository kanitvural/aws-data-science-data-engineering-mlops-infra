from aws_cdk import Stage
from constructs import Construct
from data_science.stacks.ecr_stack import ECRStack
from data_science.stacks.s3_stack import S3Stack


class DataScienceStage(Stage):
    def __init__(self, scope: Construct, id: str, env, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        S3Stack(
            self,
            f"{project_name}-s3",
            project_name=project_name,
            env=env,
        )

        ECRStack(
            self,
            f"{project_name}-ecr",
            project_name=project_name
        )
        