from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
    CfnOutput,
    Fn,
    Duration,
    aws_cognito as cognito,
)
from constructs import Construct


class ApiGatewayChatbotRestStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ENV variables
        cloudfront_url = Fn.import_value("ProjectAppCloudFrontURL")
        user_pool_id = Fn.import_value("FlightAIUserPoolId")

        # Lambdas

        # ===== 1. LAMBDA AUTHORIZER =====
        authorizer_lambda = _lambda.Function(
            self,
            "AuthorizerLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="authorizer_lambda.lambda_handler",
            code=_lambda.Code.from_asset(
                "project_app/lambda_funcs/api_gateway_chatbot_rest_lambdas/authorizer_lambda"
            ),
            timeout=Duration.seconds(30),
            environment={
                "REGION": self.region,
                "USER_POOL_ID": user_pool_id,
            },
        )

        # Grant Cognito permissions to authorizer
        authorizer_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:GetUser",
                ],
                resources=[f"arn:aws:cognito-idp:{self.region}:{self.account}:userpool/{user_pool_id}"],
            )
        )

        # ===== 2. CHAT LAMBDA =====

        agent_chat_lambda = _lambda.Function(
            self,
            "MultiAgentChatLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "project_app/lambda_funcs/api_gateway_chatbot_rest_lambdas/agent_chat_lambda"
            ),
            environment={
                "REGION": self.region,
            },
            timeout=Duration.seconds(120),
        )

        agent_chat_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:ListMemories",
                    "bedrock-agentcore:ListAgentRuntimes",
                ],
                resources=["*"],
            )
        )

        # ===== 3. HISTORY LAMBDA =====

        agent_history_lambda = _lambda.Function(
            self,
            "MultiAgentHistoryLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "project_app/lambda_funcs/api_gateway_chatbot_rest_lambdas/agent_history_lambda"
            ),
            environment={
                "REGION": self.region,
            },
            timeout=Duration.seconds(120),
        )

        agent_history_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:ListMemories",
                    "bedrock-agentcore:ListAgentRuntimes",
                ],
                resources=["*"],
            )
        )

        # ===== 4. API GATEWAY =====
        
        # Create API Gateway with CORS settings for frontend (CloudFront + localhost)
        # Using REGIONAL endpoint for lower latency and better control (instead of EDGE)
        # CORS allows sending HttpOnly cookies (allow_credentials=True)
        # so the frontend can communicate securely with Lambda Authorizer and backend

        api = apigw.RestApi(
            self,
            "MultiAgentLLMApi",
            rest_api_name="FlightAIMultiAgentLLMApi", 
            endpoint_configuration=apigw.EndpointConfiguration(types=[apigw.EndpointType.REGIONAL]),
            description="API for chatbot with Lambda Authorizer",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=[cloudfront_url, "http://localhost:3000"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=[
                    "Content-Type",
                    "Cookie",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                ],
                allow_credentials=True,
            ),
        )

    

        # ===== 5. CREATE REQUEST AUTHORIZER =====
        
        # Use Token Authorizer (Cognito, JWT, etc.) if you send the token directly from the frontend.
        # In our case, we use an HttpOnly, Secure cookie to store the token.
        # The Lambda Authorizer extracts the token from the cookie and verifies it by calling Cognito.
        # Because of this, we use a Request Authorizer instead of a Token Authorizer.
 
        request_authorizer = apigw.RequestAuthorizer(
            self,
            "CookieRequestAuthorizer",
            handler=authorizer_lambda,
            identity_sources=[
                apigw.IdentitySource.header("Cookie")
            ],
            authorizer_name="CookieRequestAuthorizer",
            results_cache_ttl=Duration.seconds(300),
        )


        # ===== 6. API RESOURCES =====

        # /chat endpoint

        chat_resource = api.root.add_resource("chat")
        chat_resource.add_method(
            "POST",
            apigw.LambdaIntegration(agent_chat_lambda, proxy=True),
            authorizer=request_authorizer,
            authorization_type=apigw.AuthorizationType.CUSTOM,
        )
        
        # /history endpoint
        history_resource = api.root.add_resource("history")
        history_resource.add_method(
            "GET",
            apigw.LambdaIntegration(agent_history_lambda, proxy=True),
            authorizer=request_authorizer,
            authorization_type=apigw.AuthorizationType.CUSTOM,
        )

        # API URL output
        CfnOutput(
            self,
            "MultiAgentLLMApiUrl",
            value=api.url,
            description="Base URL of the Multi Agent API",
            export_name=f"{project_name}-chatbot-api-url",
        )

        CfnOutput(
            self,
            "AuthorizerLambdaArn",
            value=authorizer_lambda.function_arn,
            description="Authorizer Lambda ARN",
        )
