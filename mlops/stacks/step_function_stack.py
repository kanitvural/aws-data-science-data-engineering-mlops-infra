import json
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as lambda_,
    aws_iam as iam,
)
from constructs import Construct


class StepFunctionStack(Stack):

    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        sagemaker_role_arn = f"arn:aws:iam::{self.account}:role/SageMakerExecutionRole-{project_name}-{self.account}"

        # ----------------------------------------------------------------------
        # IAM Role for Step Functions
        # ----------------------------------------------------------------------
        sfn_role = iam.Role(
            self,
            id="StepFunctionExecutionRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )

        # Lambda invoke izni
        sfn_role.add_to_policy(iam.PolicyStatement(actions=["lambda:InvokeFunction"], resources=["*"]))

        # SageMaker job oluşturma izinleri
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

        # CloudWatch logs
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
            runtime=lambda_.Runtime.PYTHON_3_10,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/evaluate_dev_endpoint"),
            # environment={"CRAWLER_NAME": f"{project_name}-processed-crawler"},
            role=evaluate_lambda_role,
            timeout=Duration.seconds(30),
        )
        register_model_lambda = lambda_.Function(
            self,
            id="RegisterModelLambda",
            runtime=lambda_.Runtime.PYTHON_3_10,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("mlops/lambda_funcs/register_model"),
            # environment={"CRAWLER_NAME": f"{project_name}-processed-crawler"},
            role=register_lambda_role,
            timeout=Duration.seconds(30),
        )

        # ----------------------------------------------------------------------
        # Step 1: Evaluate
        # ----------------------------------------------------------------------
        evaluate_step = tasks.LambdaInvoke(
            self,
            "EvaluateModel",
            lambda_function=dev_endpoint_evaluate_lambda,
            output_path="$.Payload",
        )

        # ----------------------------------------------------------------------
        # Step 2: Threshold check
        # ----------------------------------------------------------------------
        threshold = 20
        check_threshold = sfn.Choice(self, "Check Model Quality")
        pass_state = sfn.Pass(self, "ModelBelowThreshold")
        fail_state = sfn.Fail(self, "ModelAboveThreshold")

        # ----------------------------------------------------------------------
        # Step 3: Baseline (Processing Job) — Dummy örnek
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
                "dataset_format": json.dumps({"csv": {"header": True, "output_columns_position": "START"}}),
                "dataset_source": "/opt/ml/processing/input/baseline_dataset_input",
                "output_path": "/opt/ml/processing/output",
                "publish_cloudwatch_metrics": "Disabled",
            },
            processing_inputs=[
                tasks.ProcessingInput(
                    input_name="baseline_dataset_input",
                    s3_input=tasks.ProcessingS3Input(
                        s3_uri=sfn.JsonPath.format(
                            "s3://{}/{}/input/baseline/baseline.csv",
                            bucket_name,
                            sfn.JsonPath.string_at("$$.Execution.Name"),
                        ),
                        local_path="/opt/ml/processing/input/baseline_dataset_input",
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
                        s3_uri=sfn.JsonPath.format(
                            "s3://{}/{}/baseline_report", bucket_name, sfn.JsonPath.string_at("$$.Execution.Name")
                        ),
                        local_path="/opt/ml/processing/output",
                        s3_upload_mode=tasks.ProcessingS3UploadMode.END_OF_JOB,
                    ),
                ),
            ],
            cluster_config=tasks.ProcessingJobClusterConfig(
                instance_count=1,
                instance_type=sfn.InstanceType.of(sfn.InstanceClass.M5, sfn.InstanceSize.XLARGE),
                volume_size_in_gb=30,
            ),
            role=iam.Role.from_role_arn(self, "ImportedSageMakerRole", sagemaker_role_arn),
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
                sfn.Condition.number_less_than("$.Result", threshold), pass_state.next(parallel_step)
            ).otherwise(fail_state)
        ).add_catch(workflow_failed)

        # ----------------------------------------------------------------------
        # State Machine
        # ----------------------------------------------------------------------
        sm = sfn.StateMachine(
            self, "ModelWorkflow", definition=definition, timeout=Duration.minutes(30), role=sfn_role
        )

        # ----------------------------------------------------------------------
        # Output
        # ----------------------------------------------------------------------
        CfnOutput(self, "StateMachineArn", value=sm.state_machine_arn, export_name="StepFunctionStateMachineArn")
