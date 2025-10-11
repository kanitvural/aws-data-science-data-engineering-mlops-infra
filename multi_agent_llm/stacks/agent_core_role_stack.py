from aws_cdk import (
    Stack,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class BedrockAgentCoreRoleStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # AgentCore execution role
        self.agentcore_execution_role = iam.Role(
            self,
            "AgentCoreExecutionRole",
            role_name=f"AgentCoreExecutionRole-{project_name}-{self.account}",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description=f"Execution role for Bedrock AgentCore - {project_name}",
        )

        # Trust policy
        trust_policy = self.agentcore_execution_role.assume_role_policy
        if trust_policy:
            trust_policy.add_statements(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("bedrock-agentcore.amazonaws.com")],
                    actions=["sts:AssumeRole"],
                    conditions={
                        "StringEquals": {"aws:SourceAccount": self.account},
                        "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"},
                    },
                )
            )

        # ECR permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRImageAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                ],
                resources=[f"arn:aws:ecr:{self.region}:{self.account}:repository/*"],
            )
        )
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRTokenAccess",
                effect=iam.Effect.ALLOW,
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )

        # CloudWatch Logs permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup",
                ],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"],
            )
        )
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:DescribeLogGroups"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:*"],
            )
        )
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ],
            )
        )

        # X-Ray permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],
            )
        )

        # CloudWatch Metrics
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            )
        )

        # Bedrock AgentCore Runtime permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockAgentCoreRuntime",
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*"],
            )
        )

        # Bedrock AgentCore Memory/Event permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockAgentCoreMemory",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:CreateMemory",
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:ListActors",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:ListMemoryRecords",
                    "bedrock-agentcore:ListSessions",
                    "bedrock-agentcore:DeleteEvent",
                    "bedrock-agentcore:DeleteMemoryRecord",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                ],
                resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/*"],
            )
        )

        # Bedrock Identity permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockAgentCoreIdentityGetResourceApiKey",
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:GetResourceApiKey"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default/apikeycredentialprovider/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/workload-identity/{project_name}-*",
                ],
            )
        )
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockAgentCoreIdentityGetResourceOauth2Token",
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:GetResourceOauth2Token"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default/oauth2credentialprovider/*",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/workload-identity/{project_name}-*",
                ],
            )
        )

        # Workload Access Token
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockAgentCoreIdentityGetWorkloadAccessToken",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/workload-identity/{project_name}-*",
                ],
            )
        )

        # Bedrock Model Invocation
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockModelInvocation",
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:ApplyGuardrail"],
                resources=["arn:aws:bedrock:*::foundation-model/*", f"arn:aws:bedrock:{self.region}:{self.account}:*"],
            )
        )

        # S3 permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                resources=["*"],
            )
        )

        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="DynamoDBAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:DescribeTable",
                ],
                resources=["*"],
            )
        )

        # SSM Parameter Store permissions
        self.agentcore_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/{project_name}/*"],
            )
        )

        # Output
        CfnOutput(
            self,
            "AgentCoreExecutionRoleArn",
            value=self.agentcore_execution_role.role_arn,
            description="Bedrock AgentCore Execution Role ARN",
            export_name=f"{project_name}-agentcore-execution-role-arn",
        )
