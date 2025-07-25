from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codebuild as codebuild,
    aws_iam as iam,
)
from constructs import Construct
from .data_science_stage import DataScienceStage


class CDKDataSciencePipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Context'ten parametreleri al
        project_name = self.node.try_get_context("project_name") or "data-science"
        # notification_email = self.node.try_get_context("notification_email")

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "datascience"
        connection_arn = self.node.try_get_context("githubConnectionArn")

        # Source aşaması
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
                "cdk synth",
            ],
        )

        # Pipeline'ı oluştur
        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKDataSciencePipeline",
            synth=synth_step,
        )

        # DataScienceStage parametrelerle oluştur
        data_science_stage = DataScienceStage(
            self,
            id="DataScienceStage", 
            project_name=project_name,
        )
        

        # 2. Stage: ECR'ye Docker image pushla

        build_and_push_image = pipelines_.CodeBuildStep(
            "BuildAndPushImageToECR",
            input=source,
            build_environment=codebuild.BuildEnvironment(privileged=True),
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
                f"docker build --build-arg REGION={self.region} -t {project_name}-repository-{self.account}:latest ./data_science/train_container/",
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
        
        pipeline_stage = pipeline.add_stage(data_science_stage)
        pipeline_stage.add_post(build_and_push_image)
        
        
        # pipeline_stage_post_build = pipeline_stage.add_post(build_and_push_image)
        # pipeline_stage_post_build.add_post(run_sagemaker_pipeline)

        # # 3. Stage: SageMaker pipeline çalıştır
        # run_sagemaker_pipeline = pipelines_.CodeBuildStep(
        #     "RunSageMakerPipeline",
        #     input=source,
        #     commands=[
        #         "cd sagemaker",
        #         "pip install -r requirements.txt",
        #         "python run_pipeline.py"
        #     ],
        #     role_policy_statements=[
        #         iam.PolicyStatement(
        #             actions=[
        #                 "sagemaker:StartPipelineExecution",
        #                 "sagemaker:DescribePipeline",
        #                 "sagemaker:DescribePipelineExecution",
        #                 "sagemaker:ListPipelineExecutions",
        #                 "s3:PutObject",
        #                 "s3:GetObject",
        #                 "s3:ListBucket"
        #             ],
        #             resources=["*"]
        #         )
        #     ]
        # )

        # # Stage'leri post olarak sırayla ekle
        # pipeline.add_stage(pipelines_.Stage(self, "BuildAndPushStage")).add_post(build_and_push_image)
        # pipeline.add_stage(pipelines_.Stage(self, "SageMakerPipelineStage")).add_post(run_sagemaker_pipeline)
        
        # pipeline.add_stage(data_science_stage)
