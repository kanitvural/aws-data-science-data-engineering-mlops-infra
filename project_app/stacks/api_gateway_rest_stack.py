from aws_cdk import Stack, aws_lambda as _lambda, aws_apigateway as apigw, aws_iam as iam, Fn, CfnOutput, Duration
from constructs import Construct


class ApiGatewayRestStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Cognito APP_CLIENT_ID import
        app_client_id = Fn.import_value("FlightAIUserPoolClientId")
        cloudfront_url = Fn.import_value("ProjectAppCloudFrontURL")

        # ===== AUTH LAMBDAS =====
        flightai_auth_lambda = _lambda.Function(
            self,
            "FlightAIAuthLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("project_app/lambda_funcs/api_gateway_rest_lambdas/flightai_auth_lambda"),
            environment={
                "REGION": self.region,
                "APP_CLIENT_ID": app_client_id,
            },
        )

        flightai_user_lambda = _lambda.Function(
            self,
            "FlightAIUserLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("project_app/lambda_funcs/api_gateway_rest_lambdas/flightai_user_lambda"),
            environment={
                "REGION": self.region,
                "APP_CLIENT_ID": app_client_id,
            },
        )

        flightai_auth_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminConfirmSignUp",
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminRespondToAuthChallenge",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:SignUp",
                    "cognito-idp:ConfirmSignUp",
                    "cognito-idp:ForgotPassword",
                    "cognito-idp:ConfirmForgotPassword",
                ],
                resources=["*"],
            )
        )

        flightai_user_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminConfirmSignUp",
                    "cognito-idp:AdminInitiateAuth",
                    "cognito-idp:AdminRespondToAuthChallenge",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:SignUp",
                    "cognito-idp:ConfirmSignUp",
                    "cognito-idp:ForgotPassword",
                    "cognito-idp:ConfirmForgotPassword",
                ],
                resources=["*"],
            )
        )

        # ===== CHATBOT LAMBDAS =====

        agent_chat_lambda = _lambda.Function(
            self,
            "MultiAgentChatLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("project_app/lambda_funcs/api_gateway_rest_lambdas/agent_chat_lambda"),
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

        agent_history_lambda = _lambda.Function(
            self,
            "MultiAgentHistoryLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("project_app/lambda_funcs/api_gateway_rest_lambdas/agent_history_lambda"),
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
            id="FlightAIRestApiId",
            rest_api_name="FlightAIRestApi",
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

        # /auth resource
        auth_res = api.root.add_resource("auth")

        # /auth/login
        auth_login = auth_res.add_resource("login")
        auth_login.add_method("POST", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /auth/logout
        auth_logout = auth_res.add_resource("logout")
        auth_logout.add_method("POST", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /auth/me
        auth_me = auth_res.add_resource("me")
        auth_me.add_method("GET", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /auth/refresh
        auth_refresh = auth_res.add_resource("refresh")
        auth_refresh.add_method("POST", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /user resource
        user_res = api.root.add_resource("user")

        # /user/confirm
        user_confirm = user_res.add_resource("confirm")
        user_confirm.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # /user/confirm-forgot-password
        user_confirm_forgot = user_res.add_resource("confirm-forgot-password")
        user_confirm_forgot.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # /user/forgot-password
        user_forgot = user_res.add_resource("forgot-password")
        user_forgot.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # /user/signup
        user_signup = user_res.add_resource("signup")
        user_signup.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # CHATBOT

        # /chat endpoint
        chat_resource = api.root.add_resource("chat")
        chat_resource.add_method("POST", apigw.LambdaIntegration(agent_chat_lambda, proxy=True))

        # /history endpoint
        history_resource = api.root.add_resource("history")
        history_resource.add_method("GET", apigw.LambdaIntegration(agent_history_lambda, proxy=True))

        # API URL output
        CfnOutput(
            self,
            "FlightAIAuthApiUrl",
            value=api.url,
            description="Base URL of the FlightAI Auth API",
            export_name=f"{project_name}-auth-api-url",
        )
