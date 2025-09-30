from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_ssm as ssm,
    Fn,
)
from constructs import Construct
from .multi_agent_llm_stage import MultiAgentLLMStage


class CDKLLMPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "multi-agent-llm"
        pipeline_name = f"{project_name}-pipeline-{self.account}"

        # ENV VARIABLES

        openai_api_key = ssm.StringParameter.from_string_parameter_attributes(
            self, "OpenAIApiKey", parameter_name=f"/{project_name}/openai-api-key"
        ).string_value

        ecr_repository_arn = (
            f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest"
        )
        agentcore_execution_role_arn = (
            f"arn:aws:iam::{self.account}:role/AgentCoreExecutionRole-{project_name}-{self.account}"
        )

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "llm"
        connection_arn = self.node.try_get_context("githubConnectionArn")

        source = pipelines_.CodePipelineSource.connection(
            repo_string=github_repo,
            branch=github_branch,
            connection_arn=connection_arn,
        )

        synth_step = pipelines_.ShellStep(
            "Synth",
            input=source,
            commands=[
                "npm install -g aws-cdk",
                "pip install --upgrade pip",
                "pip install -r requirements.txt",
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=llm",
            ],
        )

        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKMultiAgentLLMPipeline",
            pipeline_name=pipeline_name,
            synth=synth_step,
        )

        multi_agent_llm_infra_stage = MultiAgentLLMStage(
            self,
            id="MultiAgentLLMInfraStage",
            project_name=project_name,
        )
        
        create_bedrock_agent_core_endpoint = pipelines_.CodeBuildStep(
    "CreateBedrockAgentCoreEndpoint",
    input=source,
    build_environment=codebuild.BuildEnvironment(
        compute_type=codebuild.ComputeType.SMALL,
        build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
        privileged=True,
    ),
    commands=[
        "echo '🚀 Setting up Bedrock AgentCore deployment...'",
        "echo '📦 Installing required packages...'",
        "cd multi_agent_llm/core",
        "pip install --upgrade pip",
        "pip install boto3 openai-agents bedrock-agentcore bedrock-agentcore-starter-toolkit python-dotenv pandas",
        "echo '⚙️ Configuring AgentCore agent...'",
        (
            "agentcore configure "
            "--entrypoint flight_multi_agent.py "
            "--name flight_multi_agent "
            "--execution-role $AGENTCORE_EXECUTION_ROLE_ARN "
            "--ecr $ECR_REPOSITORY "
            "--requirements-file requirements.txt "
            "--authorizer-config 'null' "
            "--request-header-allowlist '' "
            "--region $REGION "
            "--non-interactive"
        ),
        "echo '🔨 Launching AgentCore agent...'",
        "export OPENAI_API_KEY=$OPENAI_API_KEY",
        "agentcore launch --env OPENAI_API_KEY=$OPENAI_API_KEY",
        "echo '✅ AgentCore deployment completed successfully!'",
    ],
    env={
        "REGION": self.region,
        "OPENAI_API_KEY": openai_api_key,
        "ECR_REPOSITORY": ecr_repository_arn,
        "AGENTCORE_EXECUTION_ROLE_ARN": agentcore_execution_role_arn,
    },
    role_policy_statements=[
        iam.PolicyStatement(
            actions=[
                "ssm:GetParameter",
                "ssm:GetParameters",
            ],
            resources=["*"],
        ),
        # ECR
        iam.PolicyStatement(
            actions=[
                "ecr:CreateRepository",
                "ecr:DescribeRepositories",
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:PutImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
            ],
            resources=["*"],
        ),
        # CodeBuild - EKSİK OLAN KISIM!
        iam.PolicyStatement(
            actions=[
                "codebuild:CreateProject",
                "codebuild:UpdateProject",
                "codebuild:BatchGetProjects",
                "codebuild:StartBuild",
                "codebuild:BatchGetBuilds",
                "codebuild:DeleteProject",
            ],
            resources=[
                f"arn:aws:codebuild:{self.region}:{self.account}:project/bedrock-agentcore-*"
            ],
        ),
        # IAM role
        iam.PolicyStatement(
            actions=[
                "iam:CreateRole",
                "iam:GetRole",
                "iam:PassRole",
                "iam:AttachRolePolicy",
                "iam:PutRolePolicy",
            ],
            resources=[
                f"arn:aws:iam::{self.account}:role/BedrockAgentCore*",
                f"arn:aws:iam::{self.account}:role/AmazonBedrockAgentCoreSDKCodeBuild-*",
            ],
        ),
        # Bedrock AgentCore
        iam.PolicyStatement(
            actions=[
                "bedrock-agentcore:CreateRuntime",
                "bedrock-agentcore:UpdateRuntime",
                "bedrock-agentcore:GetRuntime",
                "bedrock-agentcore:DeleteRuntime",
                "bedrock-agentcore:InvokeAgentRuntime",
                "bedrock-agentcore:ListRuntimes",
            ],
            resources=["*"],
        ),
        # Lambda
        iam.PolicyStatement(
            actions=[
                "lambda:CreateFunction",
                "lambda:UpdateFunctionCode",
                "lambda:UpdateFunctionConfiguration",
                "lambda:GetFunction",
                "lambda:InvokeFunction",
            ],
            resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:*"],
        ),
        # S3
        iam.PolicyStatement(
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:CreateBucket",
            ],
            resources=["*"],
        ),
        # Logs - CodeBuild için gerekli
        iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/codebuild/*"],
        ),
    ],
)

        multi_agent_llm_infra_deploy = pipeline.add_stage(multi_agent_llm_infra_stage)
        multi_agent_llm_infra_deploy.add_post(create_bedrock_agent_core_endpoint)
