from aws_cdk import Stage
from constructs import Construct
from mlops.stacks.sm_prod_autoscaling_stack import SMProdAutoScalingStack


class SMProdAutoScalingStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, autoscaling_config: dict, **kwargs):
        super().__init__(scope, id, **kwargs)

        SMProdAutoScalingStack(
            self,
            id="SMProdAutoScalingStage",
            project_name=project_name,
            autoscaling_config=autoscaling_config,
        )
