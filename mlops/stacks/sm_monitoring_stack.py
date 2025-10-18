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


class SMMonitoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        project_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Import endpoint name
        endpoint_name = Fn.import_value(f"{project_name}-prod-endpoint-name")
        
        # Optional: Import SNS topic if you have one for alerts
        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")
        sns_topic = sns.Topic.from_topic_arn(self, "ImportedSNSTopic", sns_topic_arn)

        # ============================================
        # SAGEMAKER ENDPOINT DASHBOARD
        # ============================================

        dashboard = cloudwatch.Dashboard(
            self,
            "SageMakerEndpointDashboard",
            dashboard_name=f"{project_name}-sagemaker-dashboard"
        )

        # Metrics
        invocations_metric = cloudwatch.Metric(
            namespace="AWS/SageMaker",
            metric_name="Invocations",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Sum",
            period=Duration.minutes(1),
            label="Total Invocations"
        )

        invocations_per_instance_metric = cloudwatch.Metric(
            namespace="AWS/SageMaker",
            metric_name="InvocationsPerInstance",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Sum",
            period=Duration.minutes(1),
            label="Invocations Per Instance"
        )

        model_latency_metric = cloudwatch.Metric(
            namespace="AWS/SageMaker",
            metric_name="ModelLatency",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Average",
            period=Duration.minutes(1),
            label="Avg Model Latency (ms)",
            unit=cloudwatch.Unit.MILLISECONDS
        )

        overhead_latency_metric = cloudwatch.Metric(
            namespace="AWS/SageMaker",
            metric_name="OverheadLatency",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Average",
            period=Duration.minutes(1),
            label="Overhead Latency (ms)",
            unit=cloudwatch.Unit.MILLISECONDS
        )

        model_setup_time_metric = cloudwatch.Metric(
            namespace="AWS/SageMaker",
            metric_name="ModelSetupTime",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Average",
            period=Duration.minutes(5),
            label="Model Setup Time (ms)"
        )

        invocation_4xx_metric = cloudwatch.Metric(
            namespace="AWS/SageMaker",
            metric_name="Invocation4XXErrors",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Sum",
            period=Duration.minutes(1),
            label="4XX Errors",
            color=cloudwatch.Color.ORANGE
        )

        invocation_5xx_metric = cloudwatch.Metric(
            namespace="AWS/SageMaker",
            metric_name="Invocation5XXErrors",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Sum",
            period=Duration.minutes(1),
            label="5XX Errors",
            color=cloudwatch.Color.RED
        )

        cpu_utilization_metric = cloudwatch.Metric(
            namespace="/aws/sagemaker/Endpoints",
            metric_name="CPUUtilization",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Average",
            period=Duration.minutes(1),
            label="CPU Utilization %"
        )

        memory_utilization_metric = cloudwatch.Metric(
            namespace="/aws/sagemaker/Endpoints",
            metric_name="MemoryUtilization",
            dimensions_map={
                "EndpointName": endpoint_name,
                "VariantName": "AllTraffic"
            },
            statistic="Average",
            period=Duration.minutes(1),
            label="Memory Utilization %"
        )

        # Row 1: Invocations & Latency
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Endpoint Invocations",
                left=[invocations_metric],
                right=[invocations_per_instance_metric],
                width=12,
                height=6,
                left_y_axis=cloudwatch.YAxisProps(label="Total Invocations", show_units=False),
                right_y_axis=cloudwatch.YAxisProps(label="Per Instance", show_units=False)
            ),
            cloudwatch.GraphWidget(
                title="Model Latency (ms)",
                left=[model_latency_metric, overhead_latency_metric],
                width=12,
                height=6,
                left_y_axis=cloudwatch.YAxisProps(label="Latency (ms)", show_units=False)
            )
        )

        # Row 2: Errors & Instance Count
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Invocation Errors",
                left=[invocation_4xx_metric, invocation_5xx_metric],
                width=12,
                height=6,
                left_y_axis=cloudwatch.YAxisProps(label="Error Count", min=0)
            ),
            cloudwatch.GraphWidget(
                title="Instance Metrics",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="DesiredInstanceCount",
                        dimensions_map={
                            "EndpointName": endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(1),
                        label="Desired Instances",
                        color=cloudwatch.Color.BLUE
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="RunningInstanceCount",
                        dimensions_map={
                            "EndpointName": endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(1),
                        label="Running Instances",
                        color=cloudwatch.Color.GREEN
                    )
                ],
                width=12,
                height=6
            )
        )

        # Row 3: Resource Utilization
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="CPU Utilization %",
                left=[cpu_utilization_metric],
                width=12,
                height=6,
                left_y_axis=cloudwatch.YAxisProps(min=0, max=100)
            ),
            cloudwatch.GraphWidget(
                title="Memory Utilization %",
                left=[memory_utilization_metric],
                width=12,
                height=6,
                left_y_axis=cloudwatch.YAxisProps(min=0, max=100)
            )
        )

        # Row 4: Single Value Metrics (Current Status)
        dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="Invocations (Last 5min)",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="Invocations",
                        dimensions_map={
                            "EndpointName": endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Sum",
                        period=Duration.minutes(5)
                    )
                ],
                width=6,
                height=4
            ),
            cloudwatch.SingleValueWidget(
                title="Avg Latency (Last 5min)",
                metrics=[model_latency_metric],
                width=6,
                height=4
            ),
            cloudwatch.SingleValueWidget(
                title="Current Instance Count",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/SageMaker",
                        metric_name="RunningInstanceCount",
                        dimensions_map={
                            "EndpointName": endpoint_name,
                            "VariantName": "AllTraffic"
                        },
                        statistic="Average",
                        period=Duration.minutes(1)
                    )
                ],
                width=6,
                height=4
            ),
            cloudwatch.SingleValueWidget(
                title="Error Rate %",
                metrics=[
                    cloudwatch.MathExpression(
                        expression="(m1 + m2) / m3 * 100",
                        using_metrics={
                            "m1": invocation_4xx_metric,
                            "m2": invocation_5xx_metric,
                            "m3": invocations_metric
                        },
                        label="Error Rate"
                    )
                ],
                width=6,
                height=4
            )
        )

        # ============================================
        # CLOUDWATCH ALARMS (Optional)
        # ============================================

        # if you want alarms with SNS notifications

        # # 1. High Latency Alarm
        latency_alarm = cloudwatch.Alarm(
            self,
            "HighLatencyAlarm",
            alarm_name=f"{project_name}-sagemaker-high-latency",
            metric=model_latency_metric,
            threshold=1000,  # 1 second
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="SageMaker endpoint latency > 1s"
        )
        latency_alarm.add_alarm_action(cw_actions.SnsAction(sns_topic))

        # 2. High Error Rate Alarm
        error_alarm = cloudwatch.Alarm(
            self,
            "HighErrorRateAlarm",
            alarm_name=f"{project_name}-sagemaker-high-errors",
            metric=cloudwatch.MathExpression(
                expression="(m1 + m2) / m3 * 100",
                using_metrics={
                    "m1": invocation_4xx_metric,
                    "m2": invocation_5xx_metric,
                    "m3": invocations_metric
                }
            ),
            threshold=5,  # 5% error rate
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            alarm_description="SageMaker endpoint error rate > 5%"
        )
        error_alarm.add_alarm_action(cw_actions.SnsAction(sns_topic))

        # Outputs
        CfnOutput(
            self,
            "DashboardURL",
            value=f"https://console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={project_name}-sagemaker-dashboard",
            description="SageMaker Dashboard URL"
        )

        CfnOutput(
            self,
            "DashboardName",
            value=dashboard.dashboard_name,
            description="Dashboard name"
        )