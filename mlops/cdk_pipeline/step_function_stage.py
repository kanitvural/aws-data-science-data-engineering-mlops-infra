from aws_cdk import Stage
from constructs import Construct
from mlops.stacks.step_function_stack import StepFunctionStack


class StepFunctionStage(Stage):

    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        StepFunctionStack(
            self,
            id="StepFunctionStack",
            project_name=project_name,
        )
