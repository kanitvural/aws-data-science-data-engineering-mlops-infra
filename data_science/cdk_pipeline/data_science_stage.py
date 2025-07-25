from aws_cdk import Stage
from constructs import Construct
from data_science.stacks.ecr_stack import ECRStack
from data_science.stacks.s3_stack import S3Stack


class DataScienceStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, project_name: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        S3Stack(
            self,
            "S3Infrastructure",
            project_name=project_name,
        )

        ECRStack(
            self,
            "ECRInfrastructure", 
            project_name=project_name,
        )
        