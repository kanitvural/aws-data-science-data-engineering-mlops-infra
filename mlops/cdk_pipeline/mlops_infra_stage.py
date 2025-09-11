from aws_cdk import Stage
from constructs import Construct
from mlops.stacks.ecr_stack import ECRStack
from mlops.stacks.s3_lambda_stack import S3LambdaStack
from mlops.stacks.sns_stack import SNSStack
from mlops.stacks.sagemaker_role_stack import SageMakerRoleStack



class MLOpsInfraStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        sns_stack = SNSStack(
            self,
            id="MLOpsNotificationStack",
            project_name=project_name,
            notification_email=notification_email,
        )

        s3_stack = S3LambdaStack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        ecr_stack = ECRStack(
            self,
            id="ECRInfrastructure",
            project_name=project_name,
        )
        sagemaker_role_stack = SageMakerRoleStack(
            self,
            id="SageMakerRoleStack",
            project_name=project_name,
        )
        
        s3_stack.add_dependency(sns_stack)
        ecr_stack.add_dependency(s3_stack)
        sagemaker_role_stack.add_dependency(s3_stack)

       
