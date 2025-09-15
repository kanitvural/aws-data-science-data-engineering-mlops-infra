from aws_cdk import Stage
from constructs import Construct
from project_app.stacks.s3_stack import S3Stack
from project_app.stacks.kinesis_stack import KinesisStack
from project_app.stacks.ec2_stack import EC2Stack
from project_app.stacks.lambda_stack import LambdaStack
from project_app.stacks.sns_stack import SNSStack
from project_app.stacks.dynamodb_stack import DynamoDBStack


class ProjectAppPipelineStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str = None, **kwargs):
        super().__init__(scope, id, **kwargs)

        s3_stack = S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        kinesis_stack = KinesisStack(
            self,
            id="KinesisInfrastructure",
        )

        ec2_stack = EC2Stack(
            self,
            id="EC2Infrastructure",
            project_name=project_name
        )
        
        sns_stack = SNSStack(
            self,
            id="SNSInfrastructure",
            notification_email=notification_email,
            project_name=project_name
        )
        
        dynamodb_stack = DynamoDBStack(
            self,
            id="DynamoDBInfrastructure",
            project_name=project_name  
        )
        
        lambda_stack = LambdaStack(
            self,
            id="LambdaInfrastructure"
        )

        # Dependencies
        dynamodb_stack.add_dependency(sns_stack)       
        kinesis_stack.add_dependency(dynamodb_stack)  
        lambda_stack.add_dependency(kinesis_stack)    
        s3_stack.add_dependency(lambda_stack)         
        ec2_stack.add_dependency(s3_stack)    
