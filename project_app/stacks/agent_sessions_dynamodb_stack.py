from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class AgentSessionsDynamoDBStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Session tracking table
        sessions_table = dynamodb.Table(
            self,
            id="AgentSessionsTable",
            table_name="agent-sessions",
            partition_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="expiry_time",
        )
        
        CfnOutput(
            self,
            "SessionsTableName",
            value=sessions_table.table_name,
            export_name=f"{project_name}-agent-sessions-table-name",
        )
        
        CfnOutput(
            self,
            "SessionsTableArn",
            value=sessions_table.table_arn,
            export_name=f"{project_name}-agent-sessions-table-arn",
        )