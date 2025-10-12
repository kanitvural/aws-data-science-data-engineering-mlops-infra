from aws_cdk import Stage
from constructs import Construct
from project_app.stacks.s3_stack import S3Stack
from project_app.stacks.kinesis_stack import KinesisStack
from project_app.stacks.ec2_stack import EC2Stack
from project_app.stacks.lambda_stack import LambdaStack
from project_app.stacks.sns_stack import SNSStack
from project_app.stacks.raw_dynamodb_stack import RawDynamoDBStack
from project_app.stacks.websocket_dynamodb_stack import WebSocketDynamoDBStack
from project_app.stacks.agent_sessions_dynamodb_stack import AgentSessionsDynamoDBStack
from project_app.stacks.api_gateway_websocket_stack import ApiGatewayWebSocketStack
from project_app.stacks.cognito_stack import CognitoStack
from project_app.stacks.api_gateway_rest_stack import ApiGatewayRestStack


class AppPipelineStage(Stage):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str = None, **kwargs):
        super().__init__(scope, id, **kwargs)

        # --- Stacks ---
        cognito_stack = CognitoStack(
            self,
            id="CognitoInfrastructure",
        )

        api_gateway_rest_stack = ApiGatewayRestStack(
            self,
            id="ApiGatewayRestInfrastructure",
            project_name=project_name,
        )

        s3_stack = S3Stack(
            self,
            id="S3Infrastructure",
            project_name=project_name,
        )

        kinesis_stack = KinesisStack(
            self,
            id="KinesisInfrastructure",
            project_name=project_name,
        )

        sns_stack = SNSStack(
            self,
            id="SNSInfrastructure",
            notification_email=notification_email,
            project_name=project_name,
        )

        websocket_dynamodb_stack = WebSocketDynamoDBStack(
            self,
            id="WebSocketDynamoDBInfrastructure",
            project_name=project_name,
        )

        raw_dynamodb_stack = RawDynamoDBStack(
            self,
            id="RawDynamoDBInfrastructure",
            project_name=project_name,
        )
        
        agent_sessions_dynamodb_stack = AgentSessionsDynamoDBStack(
            self,
            id="AgentSessionsDynamoDBInfrastructure",
            project_name=project_name,
        )

        lambda_stack = LambdaStack(
            self,
            id="LambdaInfrastructure",
            project_name=project_name,
        )

        api_gateway_websocket_stack = ApiGatewayWebSocketStack(
            self,
            id="ApiGatewayWebSocketInfrastructure",
            project_name=project_name,
        )

        # --- Dependencies ---
        agent_sessions_dynamodb_stack.add_dependency(cognito_stack)
        cognito_stack.add_dependency(s3_stack)
        api_gateway_rest_stack.add_dependency(cognito_stack)
        sns_stack.add_dependency(api_gateway_rest_stack)
        raw_dynamodb_stack.add_dependency(sns_stack)
        websocket_dynamodb_stack.add_dependency(sns_stack)
        api_gateway_websocket_stack.add_dependency(websocket_dynamodb_stack)
        raw_dynamodb_stack.add_dependency(api_gateway_websocket_stack)
        kinesis_stack.add_dependency(raw_dynamodb_stack)
        lambda_stack.add_dependency(kinesis_stack)
