from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codebuild as codebuild,
    aws_iam as iam,
    Fn,
)
from constructs import Construct
from .mlops_infra_stage import MLOpsInfraStage
from .sm_dev_endpoint_stage import SMDevEndpointStage
from .step_function_stage import StepFunctionStage
from .sm_prod_endpoint_stage import SMProdEndpointStage
from .sm_prod_autoscaling_stage import SMProdAutoScalingStage


class CDKMLOpsPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        project_name = self.node.try_get_context("project_name") or "mlops"
        notification_email = self.node.try_get_context("notification_email")

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "mlops"
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
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=mlops",
            ],
        )

        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKMLOpsPipeline",
            synth=synth_step,
        )

        mlops_infra_stage = MLOpsInfraStage(
            self,
            id="MLOpsInfraStage",
            project_name=project_name,
            notification_email=notification_email,
        )

        build_and_push_image = pipelines_.CodeBuildStep(
            "BuildAndPushImageToECR",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,  # 3GB RAM, 2 vCPU
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,  # Ubuntu 22.04
            ),
            commands=[
                # == install + pre_build ==
                "printenv",
                "echo Updating Packages ...",
                "pip install --upgrade pip",
                # == build ==
                "echo Build started on `date`",
                "echo Logging in to the Data Science Container Repository ...",
                f"aws ecr get-login-password --region {self.region} | docker login --username AWS --password-stdin {self.account}.dkr.ecr.{self.region}.amazonaws.com",
                "echo Building the Container image...",
                f"docker build --build-arg REGION={self.region} -t {project_name}-repository-{self.account}:latest ./mlops/inference_container/",
                f"docker tag {project_name}-repository-{self.account}:latest {self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest",
                # == post_build ==
                "echo Pushing the Container image...",
                f"docker push {self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest",
                "echo Build completed on `date`",
            ],
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=[
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:CompleteLayerUpload",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:InitiateLayerUpload",
                        "ecr:PutImage",
                        "ecr:UploadLayerPart",
                    ],
                    resources=["*"],
                )
            ],
        )

        # MLOps Infra Stage

        mlops_infra_deploy = pipeline.add_stage(mlops_infra_stage)
        mlops_infra_deploy.add_post(build_and_push_image)

        # SageMaker Dev Endpoint Deploy Stage

        sm_dev_endpoint_stage = SMDevEndpointStage(
            self,
            id="SMDevEndpointStage",
            project_name=project_name,
        )

        sm_dev_endpoint_deploy = pipeline.add_stage(sm_dev_endpoint_stage)

        # Create the Step Function Stage
        step_function_dev_endpoint_system_test_stage = StepFunctionStage(
            self,
            id="StepFunctionDevEndpointSystemTestStage",
            project_name=project_name,
        )

        sm_dev_endpoint_step_function_system_test_deploy = pipeline.add_stage(
            step_function_dev_endpoint_system_test_stage
        )

        start_step_function = pipelines_.CodeBuildStep(
            "StartDevEndpointSystemTest",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            commands=[
                "echo '🔧 Setting up Step Function executor...'",
                "pip install --upgrade pip",
                "pip install boto3",
                "python mlops/scripts/execute_state_machine.py",
            ],
            env={
                "REGION": self.region,
                "STEP_FUNCTION_NAME_SUBSTRING": "DevEndpointEvaluationWorkflow",
                "PROJECT_NAME": project_name,
            },
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=[
                        "states:ListStateMachines",
                        "states:StartExecution",
                        "states:ListExecutions",
                        "states:DescribeExecution",
                        "states:DescribeStateMachine",
                    ],
                    resources=["*"],
                )
            ],
        )

        check_approved_model_ssm_parameter = pipelines_.CodeBuildStep(
            "CheckApprovedModelSSMParameter",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            commands=[
                "echo 'Checking Model Registry for approved model...'",
                "pip install --upgrade pip",
                "pip install boto3",
                "python mlops/scripts/check_model_registry.py",
            ],
            env={
                "REGION": self.region,
                "PROJECT_NAME": project_name,
            },
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=[
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                    ],
                    resources=["*"],
                )
            ],
        )

        sm_dev_endpoint_step_function_system_test_deploy.add_post(start_step_function)
        check_approved_model_ssm_parameter.add_step_dependency(start_step_function)
        sm_dev_endpoint_step_function_system_test_deploy.add_post(check_approved_model_ssm_parameter)

        # SageMaker Prod Endpoint Deploy Stage

        sm_prod_endpoint_stage = SMProdEndpointStage(
            self,
            id="SMProdEndpointStage",
            project_name=project_name,
        )

        # SageMaker Prod Auto-Scaling Deploy Stage
        
        sm_prod_endpoint_deploy = pipeline.add_stage(sm_prod_endpoint_stage)
        
        sm_prod_autoscaling_stage = SMProdAutoScalingStage(
            self,
            id="SMProdAutoScalingStage",
            project_name=project_name,
        )

        sm_prod_autoscaling_deploy = pipeline.add_stage(sm_prod_autoscaling_stage)
