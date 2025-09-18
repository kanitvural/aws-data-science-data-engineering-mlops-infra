from aws_cdk import Stack, aws_lambda as _lambda, aws_apigateway as apigw, aws_iam as iam, CfnOutput, Fn
from constructs import Construct

class BackendStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        dynamodb_table_name = Fn.import_value(f"{project_name}-raw-flights-table-name")

        flight_lambda = _lambda.Function(
            self,
            "GetFlightsLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("project_app/lambda_funcs/backend_lambda"),
            environment={
                "TABLE_NAME": dynamodb_table_name,
                "REGION": self.region,
            },
        )

        flight_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:Scan",
                    "dynamodb:GetItem",
                ],
                resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/{dynamodb_table_name}"],
            )
        )

        # API Gateway
        api = apigw.RestApi(
            self,
            "FlightsApi",
            rest_api_name="Flights API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "OPTIONS"],
            ),
        )

        # /flights resource
        flights_resource = api.root.add_resource("flights")

        flights_resource.add_method(
            "GET",
            apigw.LambdaIntegration(flight_lambda),
        )


        # API URL output
        CfnOutput(
            self,
            "FlightsApiUrl",
            value=api.url,
            description="Base URL of the Flights API",
            export_name=f"{project_name}-flights-api-url",
        )
