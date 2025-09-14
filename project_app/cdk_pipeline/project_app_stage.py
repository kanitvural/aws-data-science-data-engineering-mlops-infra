from aws_cdk import Stage
from constructs import Construct
from project_app.stacks.s3_stack import S3Stack
from project_app.stacks.kinesis_stack import KinesisStack
from project_app.stacks.ec2_stack import EC2Stack


class ProjectAppPipelineStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str = None, **kwargs):
        super().__init__(scope, id, **kwargs)

        # S3 Stack
        s3_stack = S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        # Kinesis Stack
        kinesis_stack = KinesisStack(
            self,
            id="KinesisInfrastructure",
            project_name=project_name,
            data_bucket=s3_stack.data_bucket,
        )

        # EC2 Stack
        ec2_stack = EC2Stack(
            self,
            id="EC2Infrastructure",
        )

        # Dependencies
        kinesis_stack.add_dependency(s3_stack)
        glue_stack.add_dependency(s3_stack)
        ec2_stack.add_dependency(kinesis_stack)
