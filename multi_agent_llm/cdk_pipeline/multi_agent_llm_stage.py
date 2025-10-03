from aws_cdk import Stage
from constructs import Construct
from multi_agent_llm.stacks.s3_stack import S3Stack
from multi_agent_llm.stacks.api_gateway_rest_stack import ApiGatewayRestStack
from multi_agent_llm.stacks.ecr_stack import ECRStack
from multi_agent_llm.stacks.agent_core_role_stack import BedrockAgentCoreRoleStack
from multi_agent_llm.stacks.sns_stack import SNSStack


class MultiAgentLLMStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str,  **kwargs):
        super().__init__(scope, id, **kwargs)
        
        sns_stack = SNSStack(
            self,
            id="MLOpsNotificationStack",
            project_name=project_name,
            notification_email=notification_email,
        )
        
        agentcore_role = BedrockAgentCoreRoleStack(
            self,
            id="AgentcoreRoleInfrastructure",
            project_name=project_name
        )

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
        sns_stack.add_dependency(ecr_stack)
        ecr_stack.add_dependency(agentcore_role)
        agentcore_role.add_dependency(s3_stack)
        s3_stack.add_dependency(rest_api_stack)

