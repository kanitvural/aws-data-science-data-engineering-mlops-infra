from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct


class DynamoDBStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ----------------------------------------------------------------------
        # DynamoDB Table for Raw Flights Data
        # ----------------------------------------------------------------------
        table = dynamodb.Table(
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
        connections_table = dynamodb.Table(
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
            "DynamoDBTableName",
            value=table.table_name,
            description="DynamoDB table name for raw flights data",
            export_name=f"{project_name}-raw-flights-table-name",
        )
        
        CfnOutput(
            self,
            "WebSocketConnectionsTableName",
            value=connections_table.table_name,
            description="DynamoDB table name for WebSocket connections",
            export_name=f"{project_name}-websocket-connections-table-name",
        )
        

