from aws_cdk import Stage
from constructs import Construct
from data_science.stacks.ecr_stack import ECRStack
from data_science.stacks.s3_stack import S3Stack


class DataScienceStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        ECRStack(
            self,
            id="ECRInfrastructure", 
            project_name=project_name,
        )
        