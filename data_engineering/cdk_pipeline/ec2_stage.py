from aws_cdk import Stage
from constructs import Construct
from project_app.stacks.ec2_stack import EC2Stack


class EC2Stage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        EC2Stack(
            self,
            project_name=project_name,
            id="DataSimulatorEC2DE",
        )