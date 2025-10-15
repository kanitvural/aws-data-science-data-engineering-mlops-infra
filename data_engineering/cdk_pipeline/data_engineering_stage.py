from aws_cdk import Stage
from constructs import Construct
from data_engineering.stacks.s3_stack import S3Stack
from data_engineering.stacks.kinesis_stack import KinesisStack
from data_engineering.stacks.ec2_stack import EC2Stack
from data_engineering.stacks.glue_stack import GlueStack
from data_engineering.stacks.sns_stack import SNSStack
from data_engineering.stacks.vpc_stack import VPCStack


class DataEngineeringStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str = None, **kwargs):
        super().__init__(scope, id, **kwargs)

        vpc_stack = VPCStack(
            self,
            id="VPCInfrastructure",
        )
        
        sns_stack = SNSStack(
            self,
            id="SNSInfrastructure",
            project_name=project_name,
            notification_email=notification_email
        )
        
        s3_stack = S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        kinesis_stack = KinesisStack(
            self,
            id="KinesisInfrastructure",
            project_name=project_name,
            data_bucket=s3_stack.data_bucket,
        )

        glue_stack = GlueStack(
            self,
            id="GlueInfrastructure",
            project_name=project_name,
        )

        ec2_stack = EC2Stack(
            self,
            id="EC2Infrastructure",
            project_name=project_name
        )

        # Dependencies
        sns_stack.add_dependency(vpc_stack)
        s3_stack.add_dependency(sns_stack)
        kinesis_stack.add_dependency(s3_stack)
        glue_stack.add_dependency(s3_stack)
        glue_stack.add_dependency(sns_stack)
        ec2_stack.add_dependency(kinesis_stack)
