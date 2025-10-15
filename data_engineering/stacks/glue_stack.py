from aws_cdk import (
    Duration,
    Stack,
    aws_glue as glue,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    aws_logs as logs,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_sns as sns,
    CfnOutput,
    RemovalPolicy,
    Fn,
)
from constructs import Construct


class GlueStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        project_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        artifacts_bucket_name = Fn.import_value("ArtifactsBucketName")
        artifacts_bucket_arn = Fn.import_value("ArtifactsBucketArn")
        data_bucket_name = Fn.import_value("DataLakeBucketName")
        data_bucket_arn = Fn.import_value("DataLakeBucketArn")
        
        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")

        artifacts_bucket_name_obj = s3.Bucket.from_bucket_name(
            self, "ImportedArtifactsBucket", artifacts_bucket_name
        )  # Bucket deployment expects IBucket object

        # Deploy Glue ETL script to artifacts bucket
        try:
            s3deploy.BucketDeployment(
                self,
                id="DeployGlueScript",
                sources=[s3deploy.Source.asset("data_engineering/scripts/")],
                destination_bucket=artifacts_bucket_name_obj,
                destination_key_prefix="glue-scripts/",
            )
        except Exception as e:
            print(f"Warning: Could not deploy scripts: {e}")

        # Glue Role
        self.glue_role = iam.Role(
            self,
            id="GlueServiceRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")],
        )

        # Permissions
        self.glue_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    data_bucket_arn,
                    f"{data_bucket_arn}/*",
                    artifacts_bucket_arn,
                    f"{artifacts_bucket_arn}/*",
                ],
            )
        )

        self.glue_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        # Glue Database
        self.glue_database = glue.CfnDatabase(
            self,
            "FlightDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="flight_db",
                description="Flight events database",
            ),
        )
        
        self.glue_database.apply_removal_policy(RemovalPolicy.DESTROY)

        # Glue ETL Job
        self.etl_job = glue.CfnJob(
            self,
            "ETLJob",
            name=f"{project_name}-etl-job",
            role=self.glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{artifacts_bucket_name}/glue-scripts/spark_etl_job.py",
            ),
            default_arguments={
                "--job-bookmark-option": "job-bookmark-enable",
                "--enable-metrics": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--job-language": "python",
                "--source-bucket": data_bucket_name,
                "--target-bucket": data_bucket_name,
                "--TempDir": f"s3://{artifacts_bucket_name}/temp/",
            },
            max_capacity=2.0,
            timeout=60,
            glue_version="4.0",
        )
        
        self.etl_job.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda Role
        etl_trigger_lambda_role = iam.Role(
            self,
            id="ETLTriggerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )

        etl_trigger_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "glue:StartJobRun",
                    "glue:StartCrawler",
                ],
                resources=["*"],
            )
        )

        # Lambda to trigger Glue Job
        etl_trigger_lambda = lambda_.Function(
            self,
            id="TriggerETLJobLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("data_engineering/lambda_funcs/trigger_etl_job"),
            environment={"GLUE_JOB_NAME": f"{project_name}-etl-job"},
            role=etl_trigger_lambda_role,
            timeout=Duration.seconds(30),
        )

        # EventBridge Rule to schedule Glue Job via Lambda
        events.Rule(
            self,
            "ScheduleGlueJobRule",
            schedule=events.Schedule.cron(minute="0", hour="3"),
            targets=[targets.LambdaFunction(etl_trigger_lambda)],
        )

        # Glue Crawler
        self.processed_crawler = glue.CfnCrawler(
            self,
            id="ProcessedDataCrawler",
            name=f"{project_name}-processed-crawler",
            role=self.glue_role.role_arn,
            database_name=self.glue_database.ref,
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[glue.CfnCrawler.S3TargetProperty(path=f"s3://{data_bucket_name}/processed/flight-events/")]
            ),
        )
        
        self.processed_crawler.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda to start crawler
        start_crawler_lambda = lambda_.Function(
            self,
            "StartCrawlerLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("data_engineering/lambda_funcs/start_crawler"),
            environment={"CRAWLER_NAME": f"{project_name}-processed-crawler"},
            role=etl_trigger_lambda_role,
            timeout=Duration.seconds(30),
        )

        
        sns_topic = sns.Topic.from_topic_arn(
            self, 
            "ImportedSNSTopic", 
            sns_topic_arn
        )

        # EventBridge rule for job success
        events.Rule(
            self,
            "GlueJobSucceededRule",
            event_pattern=events.EventPattern(
                source=["aws.glue"],
                detail_type=["Glue Job State Change"],
                detail={
                    "jobName": [f"{project_name}-etl-job"],
                    "state": ["SUCCEEDED"],
                },
            ),
            targets=[
                targets.LambdaFunction(start_crawler_lambda),
                targets.SnsTopic(sns_topic),
            ],
        )

        # EventBridge rule for job failure
        events.Rule(
            self,
            "GlueJobFailedRule",
            event_pattern=events.EventPattern(
                source=["aws.glue"],
                detail_type=["Glue Job State Change"],
                detail={
                    "jobName": [f"{project_name}-etl-job"],
                    "state": ["FAILED"],
                },
            ),
            targets=[targets.SnsTopic(sns_topic)],
        )

        # Logs
        logs.LogGroup(
            self,
            "GlueJobLogGroup",
            log_group_name=f"/aws-glue/jobs/{project_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Outputs
        CfnOutput(
            self,
            "GlueDatabaseName",
            value=self.glue_database.ref,
            export_name="GlueDatabaseName",
        )
        CfnOutput(
            self,
            "GlueETLJobName",
            value=self.etl_job.ref,
            export_name="GlueETLJobName",
        )
        CfnOutput(
            self,
            "GlueTableName",
            value="flight_events",
            export_name="GlueTableName",
        )
        CfnOutput(
            self,
            "GlueRoleArn",
            value=self.glue_role.role_arn,
        )