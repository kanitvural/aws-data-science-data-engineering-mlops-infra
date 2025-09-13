from aws_cdk import Stage
from constructs import Construct
from data_science.stacks.ecr_stack import ECRStack
from data_science.stacks.s3_lambda_stack import S3LambdaStack
from data_science.stacks.sns_stack import SNSStack
from data_science.stacks.sagemaker_role_stack import SageMakerRoleStack

      
class DataScienceStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str, pipeline_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        s3_lambda_stack = S3LambdaStack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
            pipeline_name=pipeline_name
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

        s3_lambda_stack.add_dependency(sns_stack)            
        sagemaker_stack.add_dependency(s3_lambda_stack)    
        ecr_stack.add_dependency(sagemaker_stack)
        
        
