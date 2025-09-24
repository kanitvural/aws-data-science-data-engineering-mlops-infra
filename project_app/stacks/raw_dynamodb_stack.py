from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    CfnOutput,
    Fn,
    aws_lambda as lambda_,
    aws_lambda_event_sources as event_sources,
    aws_iam as iam,
)
from constructs import Construct


class RawDynamoDBStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ----------------------------------------------------------------------
        # DynamoDB Table for Raw Flights Data
        # ----------------------------------------------------------------------
        raw_flights_table= dynamodb.Table(
            self,
            id="RawFlightsTable",
            table_name="raw-flights",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.NUMBER,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # ----------------------------------------------------------------------
        # DynamoDB Table for WebSocket Connections
        # ----------------------------------------------------------------------
        websocket_connections_table = dynamodb.Table(
            self,
            id="WebSocketConnectionsTable",
            table_name="websocket-connections",
            partition_key=dynamodb.Attribute(
                name="connectionId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # On-demand
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ----------------------------------------------------------------------
        # Lambda for Raw Flights Stream Data
        # ----------------------------------------------------------------------

        flight_stream_handler_lambda_role = iam.Role(
            self,
            "FlightStreamHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )

        flight_stream_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem",
                ],
                resources=[websocket_connections_table.table_arn],
            )
        )
        flight_stream_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=["*"],
            )
        )

        api_gateway_websocket_endpoint = Fn.import_value(f"{project_name}-FlightsWebSocketEndpoint")

        flight_stream_handler_lambda = lambda_.Function(
            self,
            "FlightStreamLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset(
                "project_app/lambda_funcs/api_gateway_websocket_lambdas/flight_dynamodb_stream_lambda"
            ),
            role=flight_stream_handler_lambda_role,
            environment={
                "TABLE_NAME": websocket_connections_table.table_name,
                "REGION": self.region,
                "API_GATEWAY_WEBSOCKET_ENDPOINT": api_gateway_websocket_endpoint,
            },
        )
        flight_stream_handler_lambda.add_event_source(
            event_sources.DynamoEventSource(
                raw_flights_table,
                starting_position=lambda_.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                report_batch_item_failures=True,
            )
        )

        # ----------------------------------------------------------------------
        # Output
        # ----------------------------------------------------------------------
        CfnOutput(
            self,
            "DynamoDBTableName",
            value=raw_flights_table.table_name,
            description="DynamoDB table name for raw flights data",
            export_name=f"{project_name}-raw-flights-table-name",
        )

        CfnOutput(
            self,
            "WebSocketConnectionsTableName",
            value=websocket_connections_table.table_name,
            description="DynamoDB table name for WebSocket connections",
            export_name=f"{project_name}-websocket-connections-table-name",
        )
