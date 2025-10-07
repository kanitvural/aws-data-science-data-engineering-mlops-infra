from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct
import aws_cdk.aws_cognito as cognito


class CognitoStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        user_pool = cognito.UserPool(
            self,
            "FlightAIUserPool",
            user_pool_name="FlightAI-APP",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True, username=False, phone=False),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        user_pool_client = cognito.UserPoolClient(
            self,
            "FlightAIUserPoolClient",
            user_pool=user_pool,
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_password=True, admin_user_password=True),
        )

        CfnOutput(
            self,
            "UserPoolClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
            export_name="FlightAIUserPoolClientId",
        )
