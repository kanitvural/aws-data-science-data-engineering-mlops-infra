from aws_cdk import (
    Stack,
    Duration,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    CfnOutput,
    Fn,
)
from constructs import Construct


class MonitoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        project_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Import existing resources
        kinesis_stream_name = Fn.import_value(f"{project_name}-kinesis-stream-name")
        firehose_stream_name = Fn.import_value(f"{project_name}-firehose-stream-name")
        redshift_workgroup_name = Fn.import_value(f"{project_name}-redshift-workgroup")
        ec2_instance_id = Fn.import_value(f"{project_name}-EC2-instance-id")
        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")

        sns_topic = sns.Topic.from_topic_arn(self, "ImportedSNSTopic", sns_topic_arn)

        # ============================================
        # CLOUDWATCH DASHBOARD
        # ============================================

        dashboard = cloudwatch.Dashboard(
            self,
            "DataPipelineDashboard",
            dashboard_name=f"{project_name}-pipeline-dashboard"
        )

        # Row 1: Kinesis & Firehose Metrics
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Kinesis Stream - Incoming Records/min",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Kinesis",
                        metric_name="IncomingRecords",
                        dimensions_map={"StreamName": kinesis_stream_name},
                        statistic="Sum",
                        period=Duration.minutes(1),
                        color=cloudwatch.Color.BLUE
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Firehose - Records Delivered to S3",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Firehose",
                        metric_name="DeliveryToS3.Records",
                        dimensions_map={"DeliveryStreamName": firehose_stream_name},
                        statistic="Sum",
                        period=Duration.minutes(5),
                        color=cloudwatch.Color.GREEN
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Firehose - Data Freshness (seconds)",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Firehose",
                        metric_name="DeliveryToS3.DataFreshness",
                        dimensions_map={"DeliveryStreamName": firehose_stream_name},
                        statistic="Average",
                        period=Duration.minutes(5),
                        color=cloudwatch.Color.ORANGE
                    )
                ],
                width=8,
                height=6
            )
        )

        # Row 2: EC2 & Redshift
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="EC2 Data Simulator - CPU %",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/EC2",
                        metric_name="CPUUtilization",
                        dimensions_map={"InstanceId": ec2_instance_id},
                        statistic="Average",
                        period=Duration.minutes(5),
                        color=cloudwatch.Color.PURPLE
                    )
                ],
                left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="EC2 - Network Out (Bytes)",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/EC2",
                        metric_name="NetworkOut",
                        dimensions_map={"InstanceId": ec2_instance_id},
                        statistic="Sum",
                        period=Duration.minutes(5),
                        color=cloudwatch.Color.BLUE
                    )
                ],
                width=8,
                height=6
            ),
            cloudwatch.GraphWidget(
                title="Redshift Serverless - RPU Usage",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/Redshift-Serverless",
                        metric_name="ComputeCapacity",
                        dimensions_map={"WorkgroupName": redshift_workgroup_name},
                        statistic="Average",
                        period=Duration.minutes(5),
                        color=cloudwatch.Color.RED
                    )
                ],
                left_y_axis=cloudwatch.YAxisProps(min=0, max=10),
                width=8,
                height=6
            )
        )

        # Row 3: Single Value Metrics (Current Status)
        dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="Kinesis - Records (Last 5min)",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/Kinesis",
                        metric_name="IncomingRecords",
                        dimensions_map={"StreamName": kinesis_stream_name},
                        statistic="Sum",
                        period=Duration.minutes(5)
                    )
                ],
                width=6,
                height=4
            ),
            cloudwatch.SingleValueWidget(
                title="Firehose - Success Rate %",
                metrics=[
                    cloudwatch.MathExpression(
                        expression="m1 / m2 * 100",
                        using_metrics={
                            "m1": cloudwatch.Metric(
                                namespace="AWS/Firehose",
                                metric_name="DeliveryToS3.Success",
                                dimensions_map={"DeliveryStreamName": firehose_stream_name},
                                statistic="Sum",
                                period=Duration.minutes(5)
                            ),
                            "m2": cloudwatch.Metric(
                                namespace="AWS/Firehose",
                                metric_name="DeliveryToS3.Records",
                                dimensions_map={"DeliveryStreamName": firehose_stream_name},
                                statistic="Sum",
                                period=Duration.minutes(5)
                            )
                        },
                        label="Success Rate"
                    )
                ],
                width=6,
                height=4
            ),
            cloudwatch.SingleValueWidget(
                title="EC2 - Current CPU %",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/EC2",
                        metric_name="CPUUtilization",
                        dimensions_map={"InstanceId": ec2_instance_id},
                        statistic="Average",
                        period=Duration.minutes(1)
                    )
                ],
                width=6,
                height=4
            ),
            cloudwatch.SingleValueWidget(
                title="Redshift - Current RPU",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/Redshift-Serverless",
                        metric_name="ComputeCapacity",
                        dimensions_map={"WorkgroupName": redshift_workgroup_name},
                        statistic="Average",
                        period=Duration.minutes(1)
                    )
                ],
                width=6,
                height=4
            )
        )

        # ============================================
        # CLOUDWATCH ALARMS
        # ============================================

        # 1. Kinesis - High Iterator Age
        kinesis_alarm = cloudwatch.Alarm(
            self,
            "KinesisIteratorAgeAlarm",
            alarm_name=f"{project_name}-kinesis-iterator-age",
            metric=cloudwatch.Metric(
                namespace="AWS/Kinesis",
                metric_name="GetRecords.IteratorAgeMilliseconds",
                dimensions_map={"StreamName": kinesis_stream_name},
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=60000,  # 60 seconds
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Kinesis data processing is delayed"
        )
        kinesis_alarm.add_alarm_action(cw_actions.SnsAction(sns_topic))

        # 2. Firehose - Low Success Rate
        firehose_alarm = cloudwatch.Alarm(
            self,
            "FirehoseSuccessAlarm",
            alarm_name=f"{project_name}-firehose-delivery",
            metric=cloudwatch.Metric(
                namespace="AWS/Firehose",
                metric_name="DeliveryToS3.Success",
                dimensions_map={"DeliveryStreamName": firehose_stream_name},
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=0.95,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            alarm_description="Firehose delivery success rate < 95%"
        )
        firehose_alarm.add_alarm_action(cw_actions.SnsAction(sns_topic))

        # 3. EC2 - Status Check
        ec2_alarm = cloudwatch.Alarm(
            self,
            "EC2StatusAlarm",
            alarm_name=f"{project_name}-ec2-health",
            metric=cloudwatch.Metric(
                namespace="AWS/EC2",
                metric_name="StatusCheckFailed",
                dimensions_map={"InstanceId": ec2_instance_id},
                statistic="Maximum",
                period=Duration.minutes(5)
            ),
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_description="EC2 simulator health check failed"
        )
        ec2_alarm.add_alarm_action(cw_actions.SnsAction(sns_topic))

        # 4. Redshift - High RPU
        redshift_alarm = cloudwatch.Alarm(
            self,
            "RedshiftRPUAlarm",
            alarm_name=f"{project_name}-redshift-rpu",
            metric=cloudwatch.Metric(
                namespace="AWS/Redshift-Serverless",
                metric_name="ComputeCapacity",
                dimensions_map={"WorkgroupName": redshift_workgroup_name},
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=7,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="Redshift RPU usage near limit"
        )
        redshift_alarm.add_alarm_action(cw_actions.SnsAction(sns_topic))

        # Outputs
        CfnOutput(
            self,
            "DashboardURL",
            value=f"https://console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={project_name}-pipeline-dashboard",
            description="CloudWatch Dashboard URL"
        )

        CfnOutput(
            self,
            "DashboardName",
            value=dashboard.dashboard_name,
            description="Dashboard name"
        )