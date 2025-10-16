from aws_cdk import Stage
from constructs import Construct
from data_engineering.stacks.monitoring_stack import MonitoringStack


class MonitoringStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        MonitoringStack(
            self,
            project_name=project_name,
            id="DataMonitoringID",
        )