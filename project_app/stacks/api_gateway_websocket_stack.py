from aws_cdk import (
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigw_integrations,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    Fn,
    aws_lambda as lambda_,
    CfnOutput,
)
from constructs import Construct


class ApiGatewayWebSocketStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        websocket_table_name = Fn.import_value(f"{project_name}-websocket-connections-table-name")
        websocket_table = dynamodb.Table.from_table_name(self, "WebsocketConnectionsTable", websocket_table_name)

        # ----------------------------------------------------------------------
        # WebSocket Lambdas Role
        # ----------------------------------------------------------------------
        ws_lambda_role = iam.Role(
            self,
            "WebSocketLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        ws_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem",
                ],
                resources=[websocket_table.table_arn],
            )
        )
        ws_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=["*"],
            )
        )

        # ----------------------------------------------------------------------
        #  WebSocket Lambdas
        # ----------------------------------------------------------------------
        connect_lambda = lambda_.Function(
            self,
            "WebSocketConnectLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/api_gateway_websocket_lambdas/connect"),
            role=ws_lambda_role,
            environment={
                "TABLE_NAME": websocket_table.table_name,
                "REGION": self.region,
            },
        )

        disconnect_lambda = lambda_.Function(
            self,
            "WebSocketDisconnectLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/api_gateway_websocket_lambdas/disconnect"),
            role=ws_lambda_role,
            environment={
                "TABLE_NAME": websocket_table.table_name,
                "REGION": self.region,
            },
        )

        # ----------------------------------------------------------------------
        # WebSocket API
        # ----------------------------------------------------------------------
        ws_api = apigwv2.WebSocketApi(
            self,
            "FlightsWebSocketApi",
            api_name="FlightAIWebSocketAPI",
            route_selection_expression="request.body.action",
            connect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigw_integrations.WebSocketLambdaIntegration(
                    "ConnectIntegration",
                    connect_lambda
                )
            ),
            disconnect_route_options=apigwv2.WebSocketRouteOptions(
                integration=apigw_integrations.WebSocketLambdaIntegration(
                    "DisconnectIntegration", 
                    disconnect_lambda
                )
            ),
        )

        ws_stage = apigwv2.WebSocketStage(
            self,
            "FlightsWebSocketStage",
            web_socket_api=ws_api,
            stage_name="prod",
            auto_deploy=True,
        )

        # ----------------------------------------------------------------------
        # Outputs
        # ----------------------------------------------------------------------

        CfnOutput(
            self,
            "FlightsWebSocketEndpoint",
            value=ws_api.api_endpoint,
            description="WebSocket API Endpoint",
            export_name=f"{project_name}-websocket-api-url",
        )

        CfnOutput(
            self,
            "FlightsWebSocketManagementEndpoint",
            value=f"https://{ws_api.api_id}.execute-api.{self.region}.amazonaws.com/{ws_stage.stage_name}",
            description="WebSocket Management API Endpoint (for Lambda)",
            export_name=f"{project_name}-FlightsWebSocketManagementEndpoint",
        )

        CfnOutput(
            self,
            "WebSocketConnectLambdaName",
            value=connect_lambda.function_name,
            description="WebSocket Connect Lambda function name",
            export_name=f"{project_name}-WebSocketConnectLambdaName",
        )
        CfnOutput(
            self,
            "WebSocketDisconnectLambdaName",
            value=disconnect_lambda.function_name,
            description="WebSocket Disconnect Lambda function name",
            export_name=f"{project_name}-WebSocketDisconnectLambdaName",
        )
