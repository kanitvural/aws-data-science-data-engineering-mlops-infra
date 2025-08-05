from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codebuild as codebuild,
    aws_iam as iam,
    Fn,
)
from constructs import Construct
from .data_science_stage import DataScienceStage


class CDKDataSciencePipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Context'ten parametreleri al
        project_name = self.node.try_get_context("project_name") or "data-science"
        notification_email = self.node.try_get_context("notification_email")

        # GitHub connections information
        github_repo = "kanitvural/aws-data-science-data-engineering-mlops-infra"
        github_branch = "datascience"
        connection_arn = self.node.try_get_context("githubConnectionArn")

        # Athena ENV variables
        input_data = "flights_sample.csv"
        glue_db_name = Fn.import_value("GlueDatabaseName")
        glue_table_name = Fn.import_value("GlueTableName")
        athena_output_bucket_name = Fn.import_value("ArtifactsBucketName")
        data_science_bucket_name = f"{project_name}-bucket-{self.account}"
        data_engineering_bucket_name = Fn.import_value("DataLakeBucketName")

        # Sagemaker ENV variables
        processing_instance_count = 1
        sagemaker_execution_role_arn = (
            f"arn:aws:iam::{self.account}:role/SageMakerExecutionRole-{project_name}-{self.account}"
        )
        ecr_repository_arn = (
            f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest"
        )
        # sns_topic_arn = This value is retrieved using boto3 in sm_pipeline.py
        processing_instance_type = "ml.t3.large"
        training_instance_count = 1
        training_instance_type = "ml.t3.large"
        clarify_instance_count = 1
        clarify_instance_type = "ml.t3.large"
        rmse_threshold = 15.0
        max_jobs = 1
        max_parallel_jobs = 1

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
                "python -m pip install --upgrade pip",
                "pip install -r requirements.txt",
                "cdk synth --context @aws-cdk/core:bootstrapQualifier=ds",
            ],
        )

        pipeline = pipelines_.CodePipeline(
            self,
            id="CDKDataSciencePipeline",
            synth=synth_step,
        )

        data_science_stage = DataScienceStage(
            self, id="DataScienceStage", project_name=project_name, notification_email=notification_email
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
                "python -m pip install --upgrade pip",
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

        athena_query_step = pipelines_.CodeBuildStep(
            "AthenaSamplingAndCopy",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,  # 3GB RAM, 2 vCPU
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,  # Ubuntu 22.04
            ),
            commands=[
                "echo Starting Athena Query...",
                "python -m pip install --upgrade pip",
                "python -m pip install boto3 pandas pyarrow",
                "python data_science/scripts/athena_query.py",
            ],
            env={
                "GLUE_DB_NAME": glue_db_name,
                "GLUE_TABLE_NAME": glue_table_name,
                "ATHENA_OUTPUT_BUCKET_NAME": f"s3://{athena_output_bucket_name}/query-results/",
                "DEST_BUCKET_NAME": f"s3://{data_science_bucket_name}/athena-sample/{input_data}",
            },
            role_policy_statements=[
                # Athena permissions
                iam.PolicyStatement(
                    actions=[
                        "athena:StartQueryExecution",
                        "athena:GetQueryExecution",
                        "athena:GetQueryResults",
                        "athena:StopQueryExecution",
                        "athena:GetWorkGroup",
                    ],
                    resources=[
                        f"arn:aws:athena:{self.region}:{self.account}:workgroup/primary",
                        f"arn:aws:athena:{self.region}:{self.account}:datacatalog/*",
                    ],
                ),
                # Glue permissions
                iam.PolicyStatement(
                    actions=["glue:GetTable", "glue:GetDatabase", "glue:GetPartitions"],
                    resources=[
                        f"arn:aws:glue:{self.region}:{self.account}:catalog",
                        f"arn:aws:glue:{self.region}:{self.account}:database/*",
                        f"arn:aws:glue:{self.region}:{self.account}:table/*/*",
                    ],
                ),
                # S3 permissions
                iam.PolicyStatement(
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:ListBucket",
                        "s3:GetBucketLocation",
                    ],
                    resources=[
                        f"arn:aws:s3:::{athena_output_bucket_name}",
                        f"arn:aws:s3:::{athena_output_bucket_name}/*",
                        f"arn:aws:s3:::{data_science_bucket_name}",
                        f"arn:aws:s3:::{data_science_bucket_name}/*",
                        f"arn:aws:s3:::{data_engineering_bucket_name}",
                        f"arn:aws:s3:::{data_engineering_bucket_name}/*",
                    ],
                ),
            ],
        )

        run_sagemaker_pipeline = pipelines_.CodeBuildStep(
            "RunSageMakerPipeline",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            commands=[
                "echo Starting SageMaker Pipeline execution...",
                "python -m pip install --upgrade pip",
                "python -m pip install boto3 sagemaker",
                "cd data_science/scripts",
                "python sm_pipeline.py",
            ],
            env={
                "SAGEMAKER_EXECUTION_ROLE_ARN": sagemaker_execution_role_arn,
                "PROJECT_NAME": project_name,
                "INPUT_DATA": input_data,
                "AWS_DEFAULT_REGION": self.region,
                "ECR_REPOSITORY_URI": ecr_repository_arn,
                "S3_BUCKET_NAME": data_science_bucket_name,
                "PROCESSING_INSTANCE_COUNT": str(processing_instance_count),
                "PROCESSING_INSTANCE_TYPE": processing_instance_type,
                "TRAINING_INSTANCE_COUNT": str(training_instance_count),
                "TRAINING_INSTANCE_TYPE": training_instance_type,
                "CLARIFY_INSTANCE_COUNT": str(clarify_instance_count),
                "CLARIFY_INSTANCE_TYPE": clarify_instance_type,
                "RMSE_THRESHOLD": str(rmse_threshold),
                "MAX_JOBS": str(max_jobs),
                "MAX_PARALLEL_JOBS": str(max_parallel_jobs),
            },
            role_policy_statements=[
                # CloudFormation permissions to describe stacks
                iam.PolicyStatement(
                    actions=[
                        "cloudformation:DescribeStacks",
                        "cloudformation:ListExports",
                    ],
                    resources=["*"],
                ),
                # SageMaker permissions
                iam.PolicyStatement(
                    actions=[
                        "sagemaker:CreatePipeline",
                        "sagemaker:UpdatePipeline",
                        "sagemaker:StartPipelineExecution",
                        "sagemaker:DescribePipeline",
                        "sagemaker:DescribePipelineExecution",
                        "sagemaker:ListPipelineExecutions",
                        "sagemaker:StopPipelineExecution",
                        "sagemaker:CreateProcessingJob",
                        "sagemaker:CreateTrainingJob",
                        "sagemaker:CreateModel",
                        "sagemaker:DescribeProcessingJob",
                        "sagemaker:DescribeTrainingJob",
                        "sagemaker:DescribeModel",
                        "sagemaker:ListTrainingJobs",
                        "sagemaker:ListProcessingJobs",
                        "sagemaker:AddTags",
                        "sagemaker:ListTags",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:ListBucket",
                        "s3:GetBucketLocation",
                        "s3:DeleteObject",
                    ],
                    resources=[
                        f"arn:aws:s3:::{data_science_bucket_name}",
                        f"arn:aws:s3:::{data_science_bucket_name}/*",
                    ],
                ),
                iam.PolicyStatement(
                    actions=[
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:DescribeRepositories",
                        "ecr:DescribeImages",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=[
                        "sns:Publish",
                        "sns:GetTopicAttributes",
                        "sns:ListTopics",
                    ],
                    resources=[
                        f"arn:aws:sns:{self.region}:{self.account}:*",
                    ],
                ),
                # IAM permissions for SageMaker execution role
                iam.PolicyStatement(
                    actions=[
                        "iam:GetRole",
                        "iam:PassRole",
                    ],
                    resources=[
                        f"arn:aws:iam::{self.account}:role/SageMakerExecutionRole*",
                        f"arn:aws:iam::{self.account}:role/service-role/SageMakerExecutionRole*",
                    ],
                ),
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                    ],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/*",
                    ],
                ),
            ],
        )

        deploy_stage = pipeline.add_stage(data_science_stage)
        deploy_stage.add_post(build_and_push_image, athena_query_step)
        run_sagemaker_pipeline.add_step_dependency(build_and_push_image)
        run_sagemaker_pipeline.add_step_dependency(athena_query_step)
        deploy_stage.add_post(run_sagemaker_pipeline)
