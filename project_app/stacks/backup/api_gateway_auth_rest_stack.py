from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
    Fn,
    CfnOutput,
)
from constructs import Construct


class ApiGatewayAuthRestStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Cognito APP_CLIENT_ID import
        app_client_id = Fn.import_value("FlightAIUserPoolClientId")
        cloudfront_url = Fn.import_value("ProjectAppCloudFrontURL")

        # Lambdaları oluştur
        flightai_auth_lambda = _lambda.Function(
            self,
            "FlightAIAuthLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "project_app/lambda_funcs/api_gateway_auth_rest_lambdas/flightai_auth_lambda"
            ),
            environment={
                "REGION": self.region,
                "APP_CLIENT_ID": app_client_id,
                "CLOUDFRONT_URL":cloudfront_url
            },
        )

        flightai_user_lambda = _lambda.Function(
            self,
            "FlightAIUserLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "project_app/lambda_funcs/api_gateway_auth_rest_lambdas/flightai_user_lambda"
            ),
            environment={
                "REGION": self.region,
                "APP_CLIENT_ID": app_client_id,
                "CLOUDFRONT_URL":cloudfront_url
            },
        )

        # Cognito izinleri ayrı ayrı
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

        # API Gateway
        api = apigw.RestApi(
            self,
            "FlightAIAuthApi",
            rest_api_name="FlightAIAuthAPI",
            endpoint_configuration=apigw.EndpointConfiguration(
                types=[apigw.EndpointType.REGIONAL]
            ),
            default_cors_preflight_options=None
        )

        # /auth resource
        auth_res = api.root.add_resource("auth")
        auth_res.add_method("OPTIONS", apigw.MockIntegration())

        # /auth/login
        auth_login = auth_res.add_resource("login")
        auth_login.add_method("OPTIONS", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))
        auth_login.add_method("POST", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /auth/logout
        auth_logout = auth_res.add_resource("logout")
        auth_logout.add_method("OPTIONS", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))
        auth_logout.add_method("POST", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /auth/me
        auth_me = auth_res.add_resource("me")
        auth_me.add_method("OPTIONS", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))
        auth_me.add_method("GET", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /auth/refresh
        auth_refresh = auth_res.add_resource("refresh")
        auth_refresh.add_method("OPTIONS", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))
        auth_refresh.add_method("POST", apigw.LambdaIntegration(flightai_auth_lambda, proxy=True))

        # /user resource
        user_res = api.root.add_resource("user")
        user_res.add_method("OPTIONS", apigw.MockIntegration())

        # /user/confirm
        user_confirm = user_res.add_resource("confirm")
        user_confirm.add_method("OPTIONS", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))
        user_confirm.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # /user/confirm-forgot-password
        user_confirm_forgot = user_res.add_resource("confirm-forgot-password")
        user_confirm_forgot.add_method("OPTIONS", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))
        user_confirm_forgot.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # /user/forgot-password
        user_forgot = user_res.add_resource("forgot-password")
        user_forgot.add_method("OPTIONS", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))
        user_forgot.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # /user/signup
        user_signup = user_res.add_resource("signup")
        user_signup.add_method("OPTIONS", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))
        user_signup.add_method("POST", apigw.LambdaIntegration(flightai_user_lambda, proxy=True))

        # API URL output
        CfnOutput(
            self,
            "FlightAIAuthApiUrl",
            value=api.url,
            description="Base URL of the FlightAI Auth API",
            export_name=f"{project_name}-auth-api-url",
        )
