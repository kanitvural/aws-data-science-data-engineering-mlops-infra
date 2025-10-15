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


class WebSocketDynamoDBStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

  
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
        # Output
        # ----------------------------------------------------------------------

        CfnOutput(
            self,
            "WebSocketConnectionsTableName",
            value=websocket_connections_table.table_name,
            description="DynamoDB table name for WebSocket connections",
            export_name=f"{project_name}-websocket-connections-table-name",
        )
