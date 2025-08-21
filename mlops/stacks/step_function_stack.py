import json
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as lambda_,
    aws_iam as iam,
    Fn,
)
from constructs import Construct


class StepFunctionStack(Stack):

    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ----------------------------------------------------------------------
        # Environment Variables
        # ----------------------------------------------------------------------

        # Evaluation Lambda environment variables
        data_science_bucket_name = Fn.import_value("DataScienceBucketName")
        test_csv_key = "sagemaker-preprocess-output/test/test.csv"
        target_column = "dep_delay"
        mlops_bucket_name = f"{project_name}-bucket-{self.account}"
        rmse_threshold = 20.0
        endpoint_name = "dev-endpoint"

        # Register Lambda environment variables
        model_package_group_name = "flight-delay-model-package-group"
        model_s3_uri = "s3://data-science-bucket-058264126563/sagemaker-final-training-output/model/pipelines-7877okymrfhn-FlightsFinalTraining-6KIqJxP2g4/output/model.tar.gz"
        inference_image_uri = (
            f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest"
        )
        model_description = "XGBoost model for flight delay prediction"
        evaluation_result_s3_bucket = mlops_bucket_name
        evaluation_result_key = "dev-endpoint-evaluation-result/evaluation.json"

        # Sagemaker Baseline Processing Job variables
        sagemaker_role_arn = f"arn:aws:iam::{self.account}:role/SageMakerExecutionRole-{project_name}-{self.account}"
        baseline_input_key = "sagemaker-preprocess-output/baseline/baseline.csv"
        baseline_output_prefix = "baseline_report"
        baseline_dataset_format = json.dumps({"csv": {"header": True, "output_columns_position": "START"}})
        baseline_dataset_source = "/opt/ml/processing/input/baseline_dataset_input"
        baseline_output_path = "/opt/ml/processing/output"
        baseline_publish_metrics = "Disabled"

        # ----------------------------------------------------------------------
        # IAM Role for Step Functions
        # ----------------------------------------------------------------------
        sfn_role = iam.Role(
            self,
            id="StepFunctionExecutionRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )

        sfn_role.add_to_policy(iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=["*"]))
        sfn_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateProcessingJob",
                    "sagemaker:DescribeProcessingJob",
                    "sagemaker:StopProcessingJob",
                    "sagemaker:CreateModel",
                    "sagemaker:CreateModelPackage",
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:ListModelPackages",
                ],
                resources=["*"],
            )
        )
        sfn_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )

        # ----------------------------------------------------------------------
        # Lambda Roles
        # ----------------------------------------------------------------------
        evaluate_lambda_role = iam.Role(
            self,
            "EvaluateLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        evaluate_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:InvokeEndpoint",
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                ],
                resources=["*"],
            )
        )

        register_lambda_role = iam.Role(
            self,
            "RegisterLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        register_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateModelPackage",
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:CreateModelPackageGroup",
                    "sagemaker:DescribeModelPackageGroup",
                    "s3:GetObject",
                    "s3:ListBucket",
                ],
                resources=["*"],
            )
        )

        # ----------------------------------------------------------------------
        # Lambda Functions
        # ----------------------------------------------------------------------
        dev_endpoint_evaluate_lambda = lambda_.Function(
            self,
            id="DevEndpointEvaluateLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/evaluate_dev_endpoint"),
            environment={
                "ENDPOINT_NAME": endpoint_name,
                "TEST_DATA_S3_BUCKET": data_science_bucket_name,
                "EVALUATION_RESULT_S3_BUCKET": mlops_bucket_name,
                "TEST_CSV_KEY": test_csv_key,
                "TARGET_COLUMN": target_column,
                "RMSE_THRESHOLD": str(rmse_threshold),
            },
            role=evaluate_lambda_role,
            timeout=Duration.seconds(30),
        )

        register_model_lambda = lambda_.Function(
            self,
            id="RegisterModelLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/register_model"),
            environment={
                "MODEL_PACKAGE_GROUP_NAME": model_package_group_name,
                "MODEL_S3_URI": model_s3_uri,
                "INFERENCE_IMAGE_URI": inference_image_uri,
                "MODEL_DESCRIPTION": model_description,
                "EVALUATION_RESULT_S3_BUCKET": evaluation_result_s3_bucket,
                "EVALUATION_RESULT_KEY": evaluation_result_key,
            },
            role=register_lambda_role,
            timeout=Duration.seconds(30),
        )

        # ----------------------------------------------------------------------
        # Step 1: Evaluate
        # ----------------------------------------------------------------------
        evaluate_step = tasks.LambdaInvoke(
            self,
            "EvaluateDevEndpointModel",
            lambda_function=dev_endpoint_evaluate_lambda,
            output_path="$.Payload",
        )

        # ----------------------------------------------------------------------
        # Step 2: Threshold check
        # ----------------------------------------------------------------------
        check_threshold = sfn.Choice(self, "Check Model Quality")
        pass_state = sfn.Pass(self, "ModelBelowThreshold")
        fail_state = sfn.Fail(self, "ModelAboveThreshold")

        # ----------------------------------------------------------------------
        # Step 3: Baseline (Processing Job)
        # ----------------------------------------------------------------------
        baseline_step = tasks.SageMakerCreateProcessingJob(
            self,
            "BaselineProcessingTask",
            processing_job_name=sfn.JsonPath.format(
                f"{project_name}-baseline-{{}}", sfn.JsonPath.string_at("$$.Execution.Name")
            ),
            app_specification=tasks.ProcessingJobAppSpecification(
                image_uri=self._get_baseline_container_uri(),
                container_arguments=[],
                container_entrypoint=[],
            ),
            environment={
                "DATASET_FORMAT": baseline_dataset_format,
                "DATASET_SOURCE": baseline_dataset_source,
                "OUTPUT_PATH": baseline_output_path,
                "PUBLISH_CLOUDWATCH_METRICS": baseline_publish_metrics,
                "BASELINE_BUCKET": data_science_bucket_name,
                "BASELINE_KEY": baseline_input_key,
                "REPORT_BUCKET": mlops_bucket_name,
                "REPORT_PREFIX": baseline_output_prefix,
            },
            processing_inputs=[
                tasks.ProcessingInput(
                    input_name="baseline_dataset_input",
                    s3_input=tasks.ProcessingS3Input(
                        s3_uri=sfn.JsonPath.format("s3://{}/{}", data_science_bucket_name, baseline_input_key),
                        local_path=baseline_dataset_source,
                        s3_data_type=tasks.ProcessingS3DataType.S3_PREFIX,
                        s3_input_mode=tasks.ProcessingS3InputMode.READ_ONLY,
                        s3_compression_type=tasks.ProcessingS3CompressionType.NONE,
                    ),
                ),
            ],
            processing_outputs=[
                tasks.ProcessingOutput(
                    output_name="monitoring_output",
                    s3_output=tasks.ProcessingS3Output(
                        s3_uri=sfn.JsonPath.format("s3://{}/{}", mlops_bucket_name, baseline_output_prefix),
                        local_path=baseline_output_path,
                        s3_upload_mode=tasks.ProcessingS3UploadMode.END_OF_JOB,
                    ),
                ),
            ],
            cluster_config=tasks.ProcessingJobClusterConfig(
                instance_count=1,
                instance_type=tasks.ProcessorInstanceType("ml.m5.xlarge"),
                volume_size_in_gb=30,
            ),
            role=iam.Role.from_role_arn(
                self,
                "ImportedSageMakerRole",
                sagemaker_role_arn,
            ),
            timeout=Duration.minutes(30),
        )

        # ----------------------------------------------------------------------
        # Step 4: Register Model Lambda
        # ----------------------------------------------------------------------
        register_model_step = tasks.LambdaInvoke(
            self,
            "RegisterModel",
            lambda_function=register_model_lambda,
            output_path="$.Payload",
        )

        # ----------------------------------------------------------------------
        # Step 5: Parallel branch (Baseline + Register)
        # ----------------------------------------------------------------------
        parallel_step = sfn.Parallel(self, "FinalizeModel")
        parallel_step.branch(baseline_step)
        parallel_step.branch(register_model_step)

        # ----------------------------------------------------------------------
        # Fail state
        # ----------------------------------------------------------------------
        workflow_failed = sfn.Fail(self, "WorkflowFailed")

        # ----------------------------------------------------------------------
        # State machine definition
        # ----------------------------------------------------------------------
        definition = evaluate_step.next(
            check_threshold.when(
                sfn.Condition.number_less_than("$.rmse", rmse_threshold), pass_state.next(parallel_step)
            ).otherwise(fail_state)
        ).add_catch(workflow_failed)

        # ----------------------------------------------------------------------
        # State Machine
        # ----------------------------------------------------------------------
        sm = sfn.StateMachine(
            self,
            "ModelWorkflow",
            definition=definition,
            timeout=Duration.minutes(30),
            role=sfn_role,
        )

        # ----------------------------------------------------------------------
        # Output
        # ----------------------------------------------------------------------
        CfnOutput(
            self,
            "StateMachineArn",
            value=sm.state_machine_arn,
            export_name="StepFunctionStateMachineArn",
        )
        
    def _get_baseline_container_uri(self) -> str:
        """Returns AWS Model Monitor Analyzer container URI based on the region"""
        region_to_account = {
            "eu-north-1": "895015795356",
            "me-south-1": "607024016150",
            "ap-south-1": "126357580389",
            "eu-west-3": "680080141114",
            "us-east-2": "777275614652",
            "eu-west-1": "468650794304",
            "eu-central-1": "048819808253",
            "sa-east-1": "539772159869",
            "ap-east-1": "001633400207",
            "us-east-1": "156813124566",
            "ap-northeast-2": "709848358524",
            "eu-west-2": "749857470468",
            "ap-northeast-1": "574779866223",
            "us-west-2": "159807026194",
            "us-west-1": "890145073186",
            "ap-southeast-1": "245545462676",
            "ap-southeast-2": "563025443158",
            "ca-central-1": "536280801234"
        }
        account = region_to_account.get(self.region)
        if not account:
            raise ValueError(f"No baseline container account defined for region {self.region}")
        return f"{account}.dkr.ecr.{self.region}.amazonaws.com/sagemaker-model-monitor-analyzer"