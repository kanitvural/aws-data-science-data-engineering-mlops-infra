from aws_cdk import Stage
from constructs import Construct
from data_science.stacks.ecr_stack import ECRStack
from data_science.stacks.s3_stack import S3Stack
from data_science.stacks.sns_stack import SNSStack
from data_science.stacks.sagemaker_role_stack import SageMakerRoleStack

      
class DataScienceStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        s3_stack = S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        ecr_stack = ECRStack(
            self,
            id="ECRInfrastructure",
            project_name=project_name,
        )

        sns_stack = SNSStack(
            self,
            id="SageMakerNotificationStack",
            project_name=project_name,
            notification_email=notification_email,
        )

        sagemaker_stack = SageMakerRoleStack(
            self,
            id="SageMakerRoleStack",
            project_name=project_name,
        )

        ecr_stack.add_dependency(s3_stack)
        sns_stack.add_dependency(s3_stack)
        sagemaker_stack.add_dependency(ecr_stack)
        
        
