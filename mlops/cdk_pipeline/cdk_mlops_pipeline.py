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
        
        sm_dev_endpoint_stage = SMDevEndpointStage(
            self,
            id="SMDevEndpointStage",
            project_name=project_name,
        )

        deploy_stage = pipeline.add_stage(mlops_infra_stage)
        deploy_stage.add_post(build_and_push_image)
        
        sagemaker_deploy = pipeline.add_stage(sm_dev_endpoint_stage)
        
        # İleride buraya test step'leri vs ekleyebilirsin
        # sagemaker_deploy.add_post(system_test_step)
        # prod_deploy = pipeline.add_stage(sagemaker_prod_stage)
        
        
