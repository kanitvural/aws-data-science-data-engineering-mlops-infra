# stacks/kinesis_stack.py

from aws_cdk import (
    Duration,
    Stack,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_s3 as s3,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
    RemovalPolicy,
    Fn,
)
from constructs import Construct


class KinesisStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # ✅ Import MLOps S3 bucket (Firehose target)
        mlops_bucket_name = Fn.import_value("MLOpsBucketName")
        data_bucket = s3.Bucket.from_bucket_name(
            self, "ImportedMLOpsBucket", mlops_bucket_name
        )

        # ----------------------------------------------------------------------
        # Kinesis Streams
        # ----------------------------------------------------------------------
        self.kinesis_raw = kinesis.Stream(
            self,
            id="KinesisRaw",
            stream_name="kinesis-raw",
            shard_count=1,
            retention_period=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.kinesis_processed = kinesis.Stream(
            self,
            id="KinesisProcessed",
            stream_name="kinesis-processed",
            shard_count=1,
            retention_period=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.kinesis_predicted = kinesis.Stream(
            self,
            id="KinesisPredicted",
            stream_name="kinesis-predicted",
            shard_count=1,
            retention_period=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ----------------------------------------------------------------------
        # Firehose → S3 (connected to kinesis-predicted)
        # ----------------------------------------------------------------------

        # CloudWatch Log Group for Firehose
        firehose_log_group = logs.LogGroup(
            self,
            id="FirehoseLogGroup",
            log_group_name="/aws/kinesisfirehose/raw-and-predicted-data",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        firehose_log_stream = logs.LogStream(
            self,
            id="FirehoseLogStream",
            log_group=firehose_log_group,
            log_stream_name="S3Delivery",
        )

        # IAM Role for Firehose
        firehose_role = iam.Role(
            self,
            id="FirehoseDeliveryRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonKinesisReadOnlyAccess"
                )
            ],
        )

        # S3 permissions
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:AbortMultipartUpload",
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:PutObject",
                ],
                resources=[data_bucket.bucket_arn, f"{data_bucket.bucket_arn}/*"],
            )
        )

        # CloudWatch permissions
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:PutLogEvents"],
                resources=[firehose_log_group.log_group_arn],
            )
        )

        # Firehose Delivery Stream
        self.firehose_stream = firehose.CfnDeliveryStream(
            self,
            id="RawAndPredictedFirehose",
            delivery_stream_name="raw-and-predicted-data",
            delivery_stream_type="KinesisStreamAsSource",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=self.kinesis_predicted.stream_arn,
                role_arn=firehose_role.role_arn,
            ),
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=data_bucket.bucket_arn,
                prefix="predicted/flight-events/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/",
                error_output_prefix="errors/",
                role_arn=firehose_role.role_arn,
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    size_in_m_bs=1, interval_in_seconds=30
                ),
                compression_format="GZIP",
                cloud_watch_logging_options=firehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                    enabled=True,
                    log_group_name=firehose_log_group.log_group_name,
                    log_stream_name=firehose_log_stream.log_stream_name,
                ),
                processing_configuration=firehose.CfnDeliveryStream.ProcessingConfigurationProperty(
                    enabled=True,
                    processors=[
                        firehose.CfnDeliveryStream.ProcessorProperty(
                            type="AppendDelimiterToRecord",
                            parameters=[
                                firehose.CfnDeliveryStream.ProcessorParameterProperty(
                                    parameter_name="Delimiter", parameter_value="\n"
                                )
                            ],
                        )
                    ],
                ),
            ),
        )

# ----------------------------------------------------------------------
# Outputs
# ----------------------------------------------------------------------

        # Kinesis Raw Stream
        CfnOutput(
            self,
            id="KinesisRawName",
            value=self.kinesis_raw.stream_name,
            export_name="KinesisRawName",
        )
        CfnOutput(
            self,
            id="KinesisRawArn",
            value=self.kinesis_raw.stream_arn,
            export_name="KinesisRawArn",
        )

        # Kinesis Processed Stream
        CfnOutput(
            self,
            id="KinesisProcessedName",
            value=self.kinesis_processed.stream_name,
            export_name="KinesisProcessedName",
        )
        CfnOutput(
            self,
            id="KinesisProcessedArn",
            value=self.kinesis_processed.stream_arn,
            export_name="KinesisProcessedArn",
        )

        # Kinesis Predicted Stream
        CfnOutput(
            self,
            id="KinesisPredictedName",
            value=self.kinesis_predicted.stream_name,
            export_name="KinesisPredictedName",
        )
        CfnOutput(
            self,
            id="KinesisPredictedArn",
            value=self.kinesis_predicted.stream_arn,
            export_name="KinesisPredictedArn",
        )

        # Firehose Stream
        CfnOutput(
            self,
            id="FirehoseStreamName",
            value="raw-and-predicted-data",
            export_name="FirehoseStreamName",
        )
