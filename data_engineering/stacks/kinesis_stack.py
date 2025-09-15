from aws_cdk import (
    Duration,
    Stack,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_s3 as s3,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct

class KinesisStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, data_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Kinesis Stream
        self.kinesis_stream = kinesis.Stream(
            self,
            id="FlightsEventsStream",
            stream_name=f"{project_name}-events-stream",
            shard_count=1,  
            retention_period=Duration.days(1), 
            removal_policy=RemovalPolicy.DESTROY 
        )

        # CloudWatch Log Group for Firehose
        firehose_log_group = logs.LogGroup(
            self,
            id="FirehoseLogGroup",
            log_group_name=f"/aws/kinesisfirehose/{project_name}-events-firehose",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY 
        )

        # CloudWatch Log Stream for Firehose
        firehose_log_stream = logs.LogStream(
            self,
            id="FirehoseLogStream",
            log_group=firehose_log_group,
            log_stream_name="S3Delivery"
        )

        # Firehose Delivery Stream IAM Role
        firehose_role = iam.Role(
            self,
            id="FirehoseDeliveryRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonKinesisReadOnlyAccess")
            ]
        )

        # Add S3 permissions to Firehose role
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:AbortMultipartUpload",
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:PutObject"
                ],
                resources=[
                    data_bucket.bucket_arn,
                    f"{data_bucket.bucket_arn}/*"
                ]
            )
        )

        # Add CloudWatch Logs permissions
        firehose_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:PutLogEvents"
                ],
                resources=[
                    firehose_log_group.log_group_arn
                ]
            )
        )

        # Firehose Delivery Stream
        self.firehose_stream = firehose.CfnDeliveryStream(
            self,
            id="FlightsEventsFirehose",
            delivery_stream_name=f"{project_name}-events-firehose",
            delivery_stream_type="KinesisStreamAsSource",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=self.kinesis_stream.stream_arn,
                role_arn=firehose_role.role_arn
            ),
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=data_bucket.bucket_arn,
                prefix="raw/flight-events/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/",
                error_output_prefix="errors/",
                role_arn=firehose_role.role_arn,
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    size_in_m_bs=1,  # 1 MB minimum
                    interval_in_seconds=60  # 1 minute minimum
                ),
                compression_format="GZIP",
                cloud_watch_logging_options=firehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                    enabled=True,
                    log_group_name=firehose_log_group.log_group_name,
                    log_stream_name=firehose_log_stream.log_stream_name
                )
            )
        )

        # Outputs
        CfnOutput(
            self,
            id="KinesisStreamName",
            value=self.kinesis_stream.stream_name,
            description="Kinesis Stream Name",
            export_name="KinesisStreamName"
        )

        CfnOutput(
            self,
            id="KinesisStreamArn",
            value=self.kinesis_stream.stream_arn,
            description="Kinesis Stream ARN",
            export_name="KinesisStreamArn"
        )

        CfnOutput(
            self,
            id="FirehoseStreamName",
            value=self.firehose_stream.delivery_stream_name,
            description="Firehose Delivery Stream Name",
            export_name="FirehoseStreamName"
        )