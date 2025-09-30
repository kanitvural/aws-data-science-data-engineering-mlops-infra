from aws_cdk import Stage
from constructs import Construct
from multi_agent_llm.stacks.s3_stack import S3Stack
from multi_agent_llm.stacks.api_gateway_rest_stack import ApiGatewayRestStack
from multi_agent_llm.stacks.ecr_stack import ECRStack


class MultiAgentLLMStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)


        s3_stack = S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )
        
        ecr_stack = ECRStack(
            self,
            id= "ECRInfrastructure",
            project_name=project_name
        )

        rest_api_stack = ApiGatewayRestStack(
            self,
            id="RESTAPIInfrastructure",
            project_name=project_name
        )

        # Dependencies
        ecr_stack.add_dependency(s3_stack)
        s3_stack.add_dependency(rest_api_stack)

