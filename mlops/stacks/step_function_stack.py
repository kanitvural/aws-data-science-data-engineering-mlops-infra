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
                actions=["sagemaker:InvokeEndpoint", "s3:GetObject", "s3:PutObject", "s3:ListBucket"],
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

        baseline_lambda_role = iam.Role(
            self,
            "BaselineLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        baseline_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:CreateProcessingJob",
                    "sagemaker:DescribeProcessingJob",
                    "sagemaker:StopProcessingJob",
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                ],
                resources=["*"],
            )
        )

        # ----------------------------------------------------------------------
        # Lambda Functions
        # ----------------------------------------------------------------------

        ml_layer = lambda_.LayerVersion(
            self,
            "MLDependenciesLayer",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/evaluate_dev_endpoint/lambda_layer/lambda_layer.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            description="Lambda layer with numpy, pandas",
        )

        dev_endpoint_evaluate_lambda = lambda_.Function(
            self,
            id="DevEndpointEvaluateLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/evaluate_dev_endpoint"),
            layers=[ml_layer],
            environment={
                "ENDPOINT_NAME": endpoint_name,
                "TEST_DATA_S3_BUCKET": data_science_bucket_name,
                "EVALUATION_RESULT_S3_BUCKET": mlops_bucket_name,
                "TEST_CSV_KEY": test_csv_key,
                "TARGET_COLUMN": target_column,
                "RMSE_THRESHOLD": str(rmse_threshold),
            },
            role=evaluate_lambda_role,
            timeout=Duration.minutes(1),
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
            timeout=Duration.minutes(1),
        )

        baseline_lambda = lambda_.Function(
            self,
            id="BaselineLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/sm_baseline_processing"),
            environment={
                "DATA_SCIENCE_BUCKET": data_science_bucket_name,
                "BASELINE_INPUT_KEY": baseline_input_key,
                "MLOPS_BUCKET": mlops_bucket_name,
                "BASELINE_OUTPUT_PREFIX": baseline_output_prefix,
                "REGION": self.region,
                "PROJECT_NAME": project_name,
                "SAGEMAKER_ROLE_ARN": sagemaker_role_arn,
            },
            role=baseline_lambda_role,
            timeout=Duration.minutes(5),
        )

        # ----------------------------------------------------------------------
        # Fail states
        # ----------------------------------------------------------------------
        workflow_failed = sfn.Fail(self, "WorkflowFailed")

        # ----------------------------------------------------------------------
        # Step 1: Evaluate
        # ----------------------------------------------------------------------
        evaluate_step = tasks.LambdaInvoke(
            self,
            "EvaluateDevEndpointModel",
            lambda_function=dev_endpoint_evaluate_lambda,
            output_path="$.Payload",
        )
        evaluate_step.add_catch(workflow_failed)

        # ----------------------------------------------------------------------
        # Step 2: Threshold check
        # ----------------------------------------------------------------------
        check_threshold = sfn.Choice(self, "Check Model Quality")
        pass_state = sfn.Pass(self, "ModelBelowThreshold")
        fail_state = sfn.Fail(self, "ModelAboveThreshold")

        # ----------------------------------------------------------------------
        # Step 3: Parallel branches
        # ----------------------------------------------------------------------
        baseline_step_parallel = tasks.LambdaInvoke(
            self,
            "BaselineProcessingStepParallel",
            lambda_function=baseline_lambda,
            output_path="$.Payload",
        )
        baseline_step_parallel.add_catch(sfn.Fail(self, "WorkflowFailedBaselineParallel"))

        register_model_step_parallel = tasks.LambdaInvoke(
            self,
            "RegisterModelStepParallel",
            lambda_function=register_model_lambda,
            output_path="$.Payload",
        )
        register_model_step_parallel.add_catch(sfn.Fail(self, "WorkflowFailedRegisterParallel"))

        parallel_step = sfn.Parallel(self, "FinalizeModel")
        parallel_step.branch(baseline_step_parallel)
        parallel_step.branch(register_model_step_parallel)

        # ----------------------------------------------------------------------
        # State machine definition
        # ----------------------------------------------------------------------
        definition = evaluate_step.next(
            check_threshold.when(
                sfn.Condition.number_less_than("$.rmse", rmse_threshold),
                pass_state.next(parallel_step),
            ).otherwise(fail_state)
        )

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
