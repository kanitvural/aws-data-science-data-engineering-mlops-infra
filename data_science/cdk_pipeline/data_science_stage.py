from aws_cdk import Stage
from constructs import Construct
from data_science.stacks.ecr_stack import ECRStack
from data_science.stacks.s3_stack import S3Stack
from data_science.stacks.sns_stack import SNSStack
from data_science.stacks.sagemaker_role_stack import SageMakerRoleStack


class DataScienceStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        ecr_stack = ECRStack(
            self,
            id="ECRInfrastructure",
            project_name=project_name,
        )
        self.ecr_repository_uri = ecr_stack.data_science_repo.repository_uri

        sns_stack = SNSStack(
            self,
            id="SageMakerNotificationStack",
            notification_email=notification_email,
        )
        
        self.sns_topic_arn = sns_stack.topic.topic_arn

        sagemaker_role_stack = SageMakerRoleStack(
            self,
            id="SageMakerRoleStack",
            project_name=project_name,
        )
        
        self.sagemaker_execution_role_arn = sagemaker_role_stack.sagemaker_execution_role.role_arn