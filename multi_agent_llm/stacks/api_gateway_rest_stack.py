from aws_cdk import Stack, aws_lambda as _lambda, aws_apigateway as apigw, aws_iam as iam, CfnOutput, Fn, Duration
from constructs import Construct


class ApiGatewayRestStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        agent_invoke_lambda = _lambda.Function(
            self,
            "MultiAgentInvokeLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("multi_agent_llm/lambda_funcs/agent_invoke_lambda"),
            environment={
                "REGION": self.region,
            },
            timeout=Duration.seconds(120),
        )

        agent_invoke_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                ],
                resources=["*"],
            )
        )
        
        agent_memory_get_lambda = _lambda.Function(
            self,
            "MultiAgentInvokeLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("multi_agent_llm/lambda_funcs/agent_memory_get_lambda"),
            environment={
                "REGION": self.region,
            },
            timeout=Duration.seconds(120),
        )

        agent_memory_get_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                ],
                resources=["*"],
            )
        )

        # API Gateway
        api = apigw.RestApi(
            self,
            "MultiAgentLLMApi",
            rest_api_name=f"{project_name}-api",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
            ),
        )

        # /chat resource
        chat_resource = api.root.add_resource("chat")

        chat_resource.add_method(
            "POST",
            apigw.LambdaIntegration(agent_invoke_lambda),
        )
        
        # /history resource
        chat_resource = api.root.add_resource("history")

        chat_resource.add_method(
            "GET",
            apigw.LambdaIntegration(agent_memory_get_lambda),
        )

        # API URL output
        CfnOutput(
            self,
            "MultiAgentLLMApiUrl",
            value=api.url,
            description="Base URL of the Multi Agent API",
            export_name=f"{project_name}-flights-api-url",
        )
