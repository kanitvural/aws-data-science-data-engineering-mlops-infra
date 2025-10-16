from aws_cdk import Stage
from constructs import Construct
from data_engineering.stacks.s3_stack import S3Stack
from data_engineering.stacks.kinesis_stack import KinesisStack
from data_engineering.stacks.glue_stack import GlueStack
from data_engineering.stacks.sns_stack import SNSStack
from data_engineering.stacks.vpc_stack import VPCStack
from data_engineering.stacks.redshift_stack import RedshiftStack


class DataEngineeringStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str = None, **kwargs):
        super().__init__(scope, id, **kwargs)

        vpc_stack = VPCStack(
            self,
            id="VPCInfrastructure",
        )

        sns_stack = SNSStack(
            self, id="SNSInfrastructure", project_name=project_name, notification_email=notification_email
        )

        s3_stack = S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        kinesis_stack = KinesisStack(
            self,
            id="DEKinesisInfrastructure",
            project_name=project_name,
            data_bucket=s3_stack.data_bucket,
        )

        glue_stack = GlueStack(
            self,
            id="GlueInfrastructure",
            project_name=project_name,
        )
        
        redshift_stack = RedshiftStack(
            self,
            id="RedshiftServerlessInfrastructure",
            project_name=project_name,
        )

        # Dependencies
        sns_stack.add_dependency(vpc_stack)
        s3_stack.add_dependency(sns_stack)
        kinesis_stack.add_dependency(s3_stack)
        glue_stack.add_dependency(s3_stack)
        glue_stack.add_dependency(sns_stack)
        redshift_stack.add_dependency(glue_stack)
