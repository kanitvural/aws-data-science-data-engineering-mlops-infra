
from aws_cdk import Stage
from constructs import Construct
from mlops.stacks.sm_prod_endpoint_stack  import SMProdEndpointStack


class SMProdEndpointStage(Stage):

    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.sm_prod_endpoint_stack = SMProdEndpointStack(
            self,
            "SMProdEndpointStack", 
            project_name=project_name,
        )