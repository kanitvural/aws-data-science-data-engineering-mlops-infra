from aws_cdk import Stack, pipelines as pipelines_, aws_codebuild as codebuild, aws_iam as iam, Fn
from constructs import Construct
from .project_app_stage import AppPipelineStage
from .ec2_stage import EC2Stage


class CDKAppPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "project-app"
        pipeline_name = f"{project_name}-pipeline-{self.account}"
        notification_email = self.node.try_get_context("notification_email")
        bucket_name = f"{project_name}-bucket-{self.account}"

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "app"
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
                "pip install -r requirements.txt",
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=app",
            ],
        )

        # Create the CodePipeline
        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKAppPipeline",
            pipeline_name=pipeline_name,
            synth=synth_step,
        )

        # Add the ProjectAppPipeline to the pipeline
        project_app_stage = AppPipelineStage(
            self,
            id="AppPipelineStage",
            project_name=project_name,
            notification_email=notification_email,
        )

        deploy_frontend_app = pipelines_.CodeBuildStep(
            "DeployFrontendApp",
            input=source,
            install_commands=[
                "echo '🔧 Installing Node.js 24 environment...'",
                "sudo apt-get update -y",
                "curl -fsSL https://deb.nodesource.com/setup_24.x | bash -",
                "sudo apt-get install -y nodejs",
                "node -v",
                "npm -v",
            ],
            commands=[
                "echo '📦 Navigating to frontend project and preparing .env.local with dynamic API URLs...'",
                # Project path
                "cd project_app/frontend/flight-dashboard",
                "echo '📦 Generating .env.local from API Gateway URLs...'",
                "python ../../scripts/generate_env_local.py",
                "echo '📦 Installing frontend dependencies...'",
                "npm ci",
                "echo '🏗 Building Next.js project...'",
                "npm run build",
                "echo '📤 Syncing out/ folder to S3...'",
                f"aws s3 rm s3://{project_name}-bucket-{self.account} --recursive",
                f"aws s3 cp out/ s3://{project_name}-bucket-{self.account} --recursive",
                "echo '☁️ Creating CloudFront invalidation...'",
                "python ../../scripts/cloudfront_cache_invalidation.py",
            ],
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True,
            ),
            env={"REGION": self.region, "BUCKET_NAME": bucket_name},
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=[
                        "s3:ListBucket",
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                    ],
                    resources=[
                        f"arn:aws:s3:::{project_name}-bucket-{self.account}",
                        f"arn:aws:s3:::{project_name}-bucket-{self.account}/*",
                    ],
                ),
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=["apigateway:*"],
                    resources=["*"],
                ),
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
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=["sts:GetCallerIdentity"],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=["cloudfront:*"],
                    resources=["*"],
                ),
            ],
        )
        # 1️⃣ Infra stage
        project_app_infra_deploy = pipeline.add_stage(project_app_stage)
        project_app_infra_deploy.add_post(deploy_frontend_app)

        # 2️⃣ Manual Approval EC2 Step
        ec2_stage = EC2Stage(
            self,
            id="ProjetAppEC2Stage",
            project_name=project_name,
        )

        manual_approval = pipelines_.ManualApprovalStep(
            id="ManualApprovalBeforeEC2", comment="✅ Please approve this deployment before EC2 stage starts."
        )

        ec2_deploy = pipeline.add_stage(
            stage=ec2_stage,
            pre=[manual_approval],
        )
