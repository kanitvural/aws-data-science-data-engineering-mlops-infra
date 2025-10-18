from aws_cdk import Stage
from constructs import Construct
from mlops.stacks.sm_prod_autoscaling_stack import SMProdAutoScalingStack
from mlops.stacks.sm_monitoring_stack import SMMonitoringStack


class SMProdAutoScalingStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, autoscaling_config: dict, **kwargs):
        super().__init__(scope, id, **kwargs)

        sm_prod_autoscaling_stack = SMProdAutoScalingStack(
            self,
            id="SMProdAutoScalingStage",
            project_name=project_name,
            autoscaling_config=autoscaling_config,
        )
        sm_prod_monitoring_stack = SMMonitoringStack(
            self,
            id="SMProdMonitoringStage",
            project_name=project_name,
        )
        
        sm_prod_monitoring_stack.add_dependency(sm_prod_autoscaling_stack)
