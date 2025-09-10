import uuid
from datetime import datetime
from aws_cdk import (
    Stack,
    pipelines as pipelines_,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_ssm as ssm,
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

        # Sagemaker Endpoint Instance configurations

        dev_instance_config = {
            "instance_type": "ml.t2.medium",
            "instance_count": 1,
        }

        prod_instance_config = {
            "instance_type": "ml.c5.large",
            "instance_count": 1,
            "autoscaling_min": 1,
            "autoscaling_max": 5,
        }

        autoscaling_config = {
            "autoscaling_min": 1,
            "autoscaling_max": 5,
            "policy_type": "TargetTrackingScaling",
            "target_invocations_per_instance": 750,
            "scale_in_cooldown": 60,
            "scale_out_cooldown": 60,
        }

        # Monitoring ENV Variables

        model_monitoring_config = {
            "instance_type": "ml.m5.xlarge",
            "instance_count": "1",
            "volume_size": "20",
        }

        monitor_name = "flight-delay-dataquality-monitor"
        prod_endpoint_name = f"{project_name}-prod-endpoint"
        sagemaker_role_arn = Fn.import_value(f"{project_name}-sagemaker-execution-role-arn")
        mlops_bucket = Fn.import_value("MLOpsBucketName")
        monitoring_output_path = f"s3://{mlops_bucket}/monitoring-results/"
        baseline_constraints_uri = f"s3://{mlops_bucket}/baseline_report/constraints.json"
        baseline_statistics_uri = f"s3://{mlops_bucket}/baseline_report/statistics.json"

        # SHAP ENV Variables

        shap_config = {
            "instance_type": "ml.m5.xlarge",
            "instance_count": "1",
        }

        target_column = "dep_delay"

        parameter_name = f"/{project_name}/latest-approved-model-arn"
        latest_model_package_arn = ssm.StringParameter.from_string_parameter_attributes(
            self, "LatestModelPackageArn", parameter_name=parameter_name
        ).string_value

        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        shap_output_path = f"s3://{mlops_bucket}/shap-analysis"
        shap_job_name = f"flight-delay-shap-{timestamp}-{unique_id}"
        processed_data_key = f"processed-data/flight-features-{timestamp}.csv"

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
            instance_config=dev_instance_config,
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
            instance_config=prod_instance_config,
        )

        # SageMaker Prod Auto-Scaling Deploy Stage

        sm_prod_endpoint_deploy = pipeline.add_stage(sm_prod_endpoint_stage)

        wait_for_prod_endpoint = pipelines_.CodeBuildStep(
            "WaitForProdEndpoint",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            commands=[
                "echo 'Waiting for Prod Endpoint to be InService...'",
                "pip install --upgrade pip",
                "pip install boto3",
                "python mlops/scripts/wait_for_endpoint.py",
            ],
            env={
                "REGION": self.region,
                "ENDPOINT_NAME": f"{project_name}-prod-endpoint",
            },
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=["sagemaker:DescribeEndpoint"],
                    resources=["*"],
                )
            ],
        )

        sm_prod_endpoint_deploy.add_post(wait_for_prod_endpoint)

        sm_prod_autoscaling_stage = SMProdAutoScalingStage(
            self,
            id="SMProdAutoScalingStage",
            project_name=project_name,
            autoscaling_config=autoscaling_config,
        )

        sm_prod_autoscaling_deploy = pipeline.add_stage(sm_prod_autoscaling_stage)

        # Production Deployment Success Notification
        prod_deployment_notification = pipelines_.CodeBuildStep(
            "ProdDeploymentNotification",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            commands=[
                "echo '📧 Sending Production Deployment Notification...'",
                "pip install --upgrade pip",
                "pip install boto3",
                "python mlops/scripts/send_prod_deployment_notification.py",
            ],
            env={
                "REGION": self.region,
                "PROJECT_NAME": project_name,
                "ENDPOINT_NAME": prod_endpoint_name,
                "INSTANCE_TYPE": prod_instance_config["instance_type"],
                "INSTANCE_COUNT": str(prod_instance_config["instance_count"]),
                "AUTOSCALING_MIN": str(autoscaling_config["autoscaling_min"]),
                "AUTOSCALING_MAX": str(autoscaling_config["autoscaling_max"]),
            },
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=[
                        "sns:Publish",
                        "sagemaker:DescribeEndpoint",
                        "application-autoscaling:DescribeScalableTargets",
                        "application-autoscaling:DescribeScalingPolicies",
                        "ssm:GetParameter",
                        "cloudformation:DescribeStacks",
                        "cloudformation:ListStacks",
                    ],
                    resources=["*"],
                )
            ],
        )

        # Add notification after autoscaling deployment
        sm_prod_autoscaling_deploy.add_post(prod_deployment_notification)

        # ---------------------------
        # Manual Approval #1
        # ---------------------------

        manual_approval = pipelines_.ManualApprovalStep(
            "ManualApprovalBeforeMonitoring", comment="Please approve to start Model Monitoring."
        )

        manual_approval.add_step_dependency(prod_deployment_notification)

        sm_prod_autoscaling_deploy.add_post(manual_approval)

        start_model_monitoring = pipelines_.CodeBuildStep(
            "StartModelMonitoring",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            commands=[
                "echo '🔧 Starting SageMaker Model Monitoring...'",
                "pip install --upgrade pip boto3 sagemaker",
                "python mlops/scripts/start_model_monitoring.py",
            ],
            env={
                "REGION": self.region,
                "SAGEMAKER_ROLE_ARN": sagemaker_role_arn,
                "ENDPOINT_NAME": prod_endpoint_name,
                "MONITOR_NAME": monitor_name,
                "INSTANCE_TYPE": model_monitoring_config["instance_type"],
                "INSTANCE_COUNT": str(model_monitoring_config["instance_count"]),
                "VOLUME_SIZE": str(model_monitoring_config["volume_size"]),
                "BASELINE_STATISTICS_URI": baseline_statistics_uri,
                "BASELINE_CONSTRAINTS_URI": baseline_constraints_uri,
                "MONITORING_OUTPUT_PATH": monitoring_output_path,
            },
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=[
                        "sagemaker:CreateMonitoringSchedule",
                        "sagemaker:DescribeMonitoringSchedule",
                        "sagemaker:StopMonitoringSchedule",
                        "sagemaker:ListMonitoringExecutions",
                        "sagemaker:ListEndpoints",
                        "s3:GetObject",
                        "s3:ListBucket",
                        "s3:PutObject",
                    ],
                    resources=["*"],
                )
            ],
        )

        start_model_monitoring.add_step_dependency(manual_approval)
        sm_prod_autoscaling_deploy.add_post(start_model_monitoring)

        # ---------------------------
        # Manual Approval #2
        # ---------------------------
        manual_approval_shap = pipelines_.ManualApprovalStep(
            "ManualApprovalBeforeSHAP", comment="Please approve to start SHAP Analysis."
        )

        # SHAP CodeBuild Step
        start_shap_analysis = pipelines_.CodeBuildStep(
            "StartSHAPAnalysis",
            input=source,
            build_environment=codebuild.BuildEnvironment(
                compute_type=codebuild.ComputeType.SMALL,
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
            ),
            commands=[
                "echo '🔧 Starting SHAP Analysis...'",
                "pip install --upgrade pip boto3 sagemaker pandas",
                "python mlops/scripts/start_shap_analysis.py",
            ],
            env={
                "REGION": self.region,
                "SAGEMAKER_ROLE_ARN": sagemaker_role_arn,
                "MODEL_PACKAGE_ARN": latest_model_package_arn,
                "ENDPOINT_NAME": prod_endpoint_name,
                "BUCKET": mlops_bucket,
                "TARGET_COLUMN": target_column,
                "SHAP_OUTPUT_PATH": shap_output_path,
                "SHAP_JOB_NAME": shap_job_name,
                "PROCESSED_DATA_KEY": processed_data_key,
                "INSTANCE_TYPE": shap_config["instance_type"],
                "INSTANCE_COUNT": str(shap_config["instance_count"]),
            },
            role_policy_statements=[
                iam.PolicyStatement(
                    actions=[
                        "sagemaker:DescribeEndpoint",
                        "sagemaker:InvokeEndpoint",
                        "sagemaker:CreateProcessingJob",
                        "sagemaker:DescribeProcessingJob",
                        "s3:GetObject",
                        "s3:ListBucket",
                        "s3:PutObject",
                    ],
                    resources=["*"],
                )
            ],
        )

        manual_approval_shap.add_step_dependency(start_model_monitoring)
        start_shap_analysis.add_step_dependency(manual_approval_shap)
        sm_prod_autoscaling_deploy.add_post(manual_approval_shap)
        sm_prod_autoscaling_deploy.add_post(start_shap_analysis)
