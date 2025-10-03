from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codebuild as codebuild,
    aws_iam as iam,
)
from constructs import Construct
from .multi_agent_llm_stage import MultiAgentLLMStage


class CDKLLMPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "multi-agent-llm"
        pipeline_name = f"{project_name}-pipeline-{self.account}"
        notification_email = self.node.try_get_context("notification_email")

        # ENV VARIABLES
        openai_api_key_param_name = f"/{project_name}/openai-api-key"

        ecr_repository_name = f"{project_name}-repository-{self.account}"
        ecr_image_uri = f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{ecr_repository_name}"

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
            self, id="MultiAgentLLMInfraStage", project_name=project_name, notification_email=notification_email
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
                "echo '🔑 Fetching OpenAI API Key from SSM...'",
                f"export OPENAI_API_KEY=$(aws ssm get-parameter --name {openai_api_key_param_name} --with-decryption --query Parameter.Value --output text)",
                "echo '⚙️ Configuring OpenAI Vector Store...'",
                "python utils/create_openai_vector_store.py",
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
                "agentcore launch --env OPENAI_API_KEY=$OPENAI_API_KEY",
                "echo '✅ AgentCore deployment completed successfully!'",
                "echo '📧 Preparing deployment notification...'",
               
                "export MEMORY_ID=$(aws bedrock-agentcore-control list-memories --region $REGION --query 'memories[?status==`ACTIVE`].id | [0]' --output text)",
                "export RUNTIME_ARN=$(aws bedrock-agentcore-control list-agent-runtimes --region $REGION --query 'agentRuntimes[?status==`READY`].agentRuntimeArn | [0]' --output text)",
                f"export API_URL=$(aws cloudformation describe-stacks --stack-name {project_name}-MultiAgentLLMInfraStage --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`RestApiUrl`].OutputValue' --output text)",
                f"export SNS_TOPIC_ARN=$(aws cloudformation describe-stacks --stack-name {project_name}-SNSStack --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`SNSNotificationTopicArn`].OutputValue' --output text)",
                
                """aws sns publish \\
            --topic-arn $SNS_TOPIC_ARN \\
            --subject "🚀 Flight Multi-Agent Deployed Successfully!" \\
            --message "$(cat <<EOF
        🎉 FLIGHT MULTI-AGENT DEPLOYMENT SUCCESSFUL
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ✅ Status: DEPLOYED
        📅 Time: $(date)
        🌍 Region: $REGION

        🔗 API ENDPOINTS:
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        POST ${API_URL:-YOUR_API_URL}/chat
        → Send chat messages to agent
        Body: {"prompt": "...", "sessionId": "..."}

        POST ${API_URL:-YOUR_API_URL}/history  
        → Get conversation history
        Body: {"sessionId": "..."}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        📊 RESOURCE IDs:
        Memory: ${MEMORY_ID:-N/A}
        Runtime: ${RUNTIME_ARN:-N/A}

        🧪 QUICK TEST:
        curl -X POST ${API_URL}/chat \\
        -H "Content-Type: application/json" \\
        -d '{"prompt":"Find flights IST to NYC","sessionId":"test-123"}'

        curl -X POST ${API_URL}/history \\
        -H "Content-Type: application/json" \\
        -d '{"sessionId":"test-123"}'

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        🚀 System ready for production!
        EOF
        )"
            """,
                "echo '📧 Notification sent successfully!'",
            ],
            env={
                "REGION": self.region,
                "ECR_REPOSITORY": ecr_image_uri,
                "AGENTCORE_EXECUTION_ROLE_ARN": agentcore_execution_role_arn,
            },
            role_policy_statements=[
                # SSM
                iam.PolicyStatement(
                    actions=["ssm:GetParameter"],
                    resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter{openai_api_key_param_name}"],
                ),
                # ECR - Authorization
                iam.PolicyStatement(
                    actions=["ecr:GetAuthorizationToken"],
                    resources=["*"],
                ),
                # ECR - Repository
                iam.PolicyStatement(
                    actions=[
                        "ecr:CreateRepository",
                        "ecr:DescribeRepositories",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:PutImage",
                        "ecr:InitiateLayerUpload",
                        "ecr:UploadLayerPart",
                        "ecr:CompleteLayerUpload",
                    ],
                    resources=[f"arn:aws:ecr:{self.region}:{self.account}:repository/{ecr_repository_name}"],
                ),
                # CodeBuild
                iam.PolicyStatement(
                    actions=[
                        "codebuild:CreateProject",
                        "codebuild:UpdateProject",
                        "codebuild:BatchGetProjects",
                        "codebuild:StartBuild",
                        "codebuild:BatchGetBuilds",
                        "codebuild:DeleteProject",
                    ],
                    resources=[f"arn:aws:codebuild:{self.region}:{self.account}:project/*"],
                ),
                # IAM
                iam.PolicyStatement(
                    actions=[
                        "iam:CreateRole",
                        "iam:GetRole",
                        "iam:PassRole",
                        "iam:AttachRolePolicy",
                        "iam:PutRolePolicy",
                        "iam:DeleteRolePolicy",
                        "iam:ListAttachedRolePolicies",
                        "iam:ListRolePolicies",
                    ],
                    resources=[
                        agentcore_execution_role_arn,
                        f"arn:aws:iam::{self.account}:role/AmazonBedrockAgentCoreSDKCodeBuild-*",
                        f"arn:aws:iam::{self.account}:role/agentcore-*",
                    ],
                ),
                # Lambda
                iam.PolicyStatement(
                    actions=[
                        "lambda:CreateFunction",
                        "lambda:UpdateFunctionCode",
                        "lambda:UpdateFunctionConfiguration",
                        "lambda:GetFunction",
                        "lambda:InvokeFunction",
                        "lambda:DeleteFunction",
                        "lambda:AddPermission",
                        "lambda:RemovePermission",
                    ],
                    resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:flight_multi_agent*"],
                ),
                iam.PolicyStatement(
                    actions=["s3:*"],
                    resources=["*"],
                ),
                # CloudWatch Logs
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=["bedrock:*"],
                    resources=["*"],
                ),
                # Bedrock AgentCore - FULL
                iam.PolicyStatement(
                    actions=["bedrock-agentcore:*"],
                    resources=["*"],
                ),
            ],
        )

        multi_agent_llm_infra_deploy = pipeline.add_stage(multi_agent_llm_infra_stage)
        multi_agent_llm_infra_deploy.add_post(create_bedrock_agent_core_endpoint)
