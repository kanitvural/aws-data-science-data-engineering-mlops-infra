from aws_cdk import Stage
from constructs import Construct
from mlops.stacks.sm_dev_endpoint_stack import SMDevEndpointStack


class SMDevEndpointStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, instance_config: dict, **kwargs):
        super().__init__(scope, id, **kwargs)

        SMDevEndpointStack(
            self,
            project_name=project_name,
            id="SagemakerDevEndpoint",
            instance_config=instance_config,
        )
