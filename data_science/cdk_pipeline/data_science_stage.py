from aws_cdk import Stage
from constructs import Construct
from data_science.stacks.ecr_stack import ECRStack
from data_science.stacks.s3_stack import S3Stack
from data_science.stacks.sns_stack import SNSStack


class DataScienceStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str, **kwargs):
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

        SNSStack(
            self,
            id="SageMakerNotificationStack",
            notification_email=notification_email,
        )
