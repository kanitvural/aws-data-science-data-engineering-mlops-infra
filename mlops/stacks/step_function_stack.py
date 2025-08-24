import json
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_sns as sns,
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
        rmse_threshold = 10.0
        endpoint_name = f"{project_name}-dev-endpoint"

        # Register Lambda environment variables

        parameter_name = "/data-science/final_evaluated_model_s3_dir"
        model_s3_uri = ssm.StringParameter.from_string_parameter_attributes(
            self,
            id="LatestModelPackageArn",
            parameter_name=parameter_name,
        ).string_value

        model_package_group_name = "flight-delay-model-package-group"
        inference_image_uri = (
            f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/{project_name}-repository-{self.account}:latest"
        )
        model_description = "XGBoost model for flight delay prediction"
        evaluation_result_s3_bucket = mlops_bucket_name
        evaluation_result_key = "dev-endpoint-evaluation-result/evaluation.json"

        # Sagemaker Baseline Processing Job variables
        sagemaker_role_arn = Fn.import_value(f"{project_name}-sagemaker-execution-role-arn")
        baseline_input_key = "sagemaker-preprocess-output/baseline/baseline.csv"
        baseline_output_prefix = "baseline_report"

        # SNS Topic ARN for notifications
        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")
        sns_topic = sns.Topic.from_topic_arn(self, "NotificationTopic", sns_topic_arn)

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

        sfn_role.add_to_policy(
            iam.PolicyStatement(
                actions=["sns:Publish"],
                resources=[sns_topic_arn],
            )
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
                    "ecr:GetAuthorizationToken",
                    "ecr:DescribeRepositories",
                    "ecr:DescribeImages",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ssm:PutParameter",
                    "ssm:GetParameter",
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
                    "iam:PassRole",
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
                "REGION": self.region,
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
                "PROJECT_NAME": project_name,
                "MODEL_PACKAGE_GROUP_NAME": model_package_group_name,
                "MODEL_S3_URI": model_s3_uri,
                "INFERENCE_IMAGE_URI": inference_image_uri,
                "MODEL_DESCRIPTION": model_description,
                "EVALUATION_RESULT_S3_BUCKET": evaluation_result_s3_bucket,
                "EVALUATION_RESULT_KEY": evaluation_result_key,
                "REGION": self.region,
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
        # SNS Notification Tasks - HER BİR FAILURE İÇİN AYRI TASK
        # ----------------------------------------------------------------------
        success_notification_task = tasks.SnsPublish(
            self,
            "SuccessNotification",
            topic=sns_topic,
            message=sfn.TaskInput.from_text(
                sfn.JsonPath.format(
                    "Model evaluation completed successfully!\n\n"
                    "✅ Model Performance: PASSED\n"
                    "📊 RMSE Score: {}\n"
                    "🎯 Threshold: {}\n"
                    "📝 Status: Model has been registered and baseline processing initiated\n\n"
                    "The model is now ready for production deployment.",
                    sfn.JsonPath.string_at("$.rmse"),
                    str(rmse_threshold)
                )
            ),
            subject="Step Function Execution Successful - Model Evaluation Passed"
        )

        # Evaluate failure için ayrı notification
        evaluate_failure_notification = tasks.SnsPublish(
            self,
            "EvaluateFailureNotification",
            topic=sns_topic,
            message=sfn.TaskInput.from_text(
                "Evaluate step failed! Workflow execution terminated.\n\n"
                "❌ Step: Model Evaluation\n"
                "📝 Status: Lambda function execution failed\n\n"
                "Please check the Lambda function logs for details."
            ),
            subject="Step Function Failed - Model Evaluation Error"
        )

        # Threshold failure için ayrı notification
        threshold_failure_notification = tasks.SnsPublish(
            self,
            "ThresholdFailureNotification",
            topic=sns_topic,
            message=sfn.TaskInput.from_text(
                sfn.JsonPath.format(
                    "Model evaluation failed to meet quality threshold!\n\n"
                    "❌ Model Performance: FAILED\n"
                    "📊 RMSE Score: {}\n"
                    "🎯 Threshold: {}\n"
                    "📝 Status: Model rejected - does not meet quality standards\n\n"
                    "Please review the model training process and retrain with improved parameters.",
                    sfn.JsonPath.string_at("$.rmse"),
                    str(rmse_threshold)
                )
            ),
            subject="Step Function Failed - Model Quality Threshold Not Met"
        )

        # Baseline failure için ayrı notification
        baseline_failure_notification = tasks.SnsPublish(
            self,
            "BaselineFailureNotification",
            topic=sns_topic,
            message=sfn.TaskInput.from_text(
                "Baseline processing step failed! Workflow execution terminated.\n\n"
                "❌ Step: Baseline Processing\n"
                "📝 Status: Lambda function execution failed\n\n"
                "Please check the Lambda function logs for details."
            ),
            subject="Step Function Failed - Baseline Processing Error"
        )

        # Register model failure için ayrı notification
        register_failure_notification = tasks.SnsPublish(
            self,
            "RegisterFailureNotification",
            topic=sns_topic,
            message=sfn.TaskInput.from_text(
                "Register model step failed! Workflow execution terminated.\n\n"
                "❌ Step: Model Registration\n"
                "📝 Status: Lambda function execution failed\n\n"
                "Please check the Lambda function logs for details."
            ),
            subject="Step Function Failed - Model Registration Error"
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
        evaluate_step.add_catch(evaluate_failure_notification.next(workflow_failed))

        # ----------------------------------------------------------------------
        # Step 2: Threshold check
        # ----------------------------------------------------------------------
        check_threshold = sfn.Choice(self, "Check Model Quality")
        pass_state = sfn.Pass(self, "ModelBelowThreshold")
        
        threshold_fail_chain = threshold_failure_notification.next(
            sfn.Fail(self, "ModelAboveThreshold")
        )

        # ----------------------------------------------------------------------
        # Step 3: Parallel branches
        # ----------------------------------------------------------------------
        baseline_step_parallel = tasks.LambdaInvoke(
            self,
            "BaselineProcessingStepParallel",
            lambda_function=baseline_lambda,
            output_path="$.Payload",
        )
        baseline_step_parallel.add_catch(baseline_failure_notification.next(workflow_failed))

        register_model_step_parallel = tasks.LambdaInvoke(
            self,
            "RegisterModelStepParallel",
            lambda_function=register_model_lambda,
            output_path="$.Payload",
        )
        register_model_step_parallel.add_catch(register_failure_notification.next(workflow_failed))

        parallel_step = sfn.Parallel(self, "FinalizeModel")
        parallel_step.branch(baseline_step_parallel)
        parallel_step.branch(register_model_step_parallel)
        parallel_step_with_success = parallel_step.next(success_notification_task)

        # ----------------------------------------------------------------------
        # State machine definition
        # ----------------------------------------------------------------------
        definition = evaluate_step.next(
            check_threshold.when(
                sfn.Condition.number_less_than("$.rmse", rmse_threshold),
                pass_state.next(parallel_step_with_success),
            ).otherwise(threshold_fail_chain)
        )

        # ----------------------------------------------------------------------
        # State Machine
        # ----------------------------------------------------------------------
        sm = sfn.StateMachine(
            self,
            "DevEndpointEvaluationWorkflow",
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