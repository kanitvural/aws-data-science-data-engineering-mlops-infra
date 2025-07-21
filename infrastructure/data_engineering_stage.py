from aws_cdk import Stage
from constructs import Construct
from infrastructure.data_engineering.stacks.s3_stack import S3Stack
from infrastructure.data_engineering.stacks.kinesis_stack import KinesisStack
from infrastructure.data_engineering.stacks.ec2_stack import EC2Stack
from infrastructure.data_engineering.stacks.glue_stack import GlueStack

class DataEngineeringStage(Stage):
    def __init__(self, scope: Construct, id: str, env, project_name: str, notification_email: str = None, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # S3 Stack
        s3_stack = S3Stack(
            self, 
            f"{project_name}-s3",
            project_name=project_name,
            env=env,
        )
        
        # Kinesis Stack
        kinesis_stack = KinesisStack(
            self, 
            f"{project_name}-kinesis",
            project_name=project_name,
            data_bucket=s3_stack.data_bucket,
            env=env
        )
        
        # Glue Stack
        glue_stack = GlueStack(
            self, 
            f"{project_name}-glue",
            project_name=project_name,
            data_bucket=s3_stack.data_bucket,
            artifacts_bucket=s3_stack.artifacts_bucket,
            notification_email=notification_email,
            env=env
        )
        
        # EC2 Stack
        ec2_stack = EC2Stack(
            self, 
            f"{project_name}-ec2",
            project_name=project_name,
            kinesis_stream=kinesis_stack.kinesis_stream,
            env=env
        )
        
        # Dependencies
        kinesis_stack.add_dependency(s3_stack)
        glue_stack.add_dependency(s3_stack)
        ec2_stack.add_dependency(kinesis_stack)