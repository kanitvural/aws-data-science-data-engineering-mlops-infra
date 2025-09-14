from aws_cdk import (
    Stack,
    aws_applicationautoscaling as autoscaling,
    Fn,
)
from constructs import Construct


# Invocation-based Scaling Policy for testing auto-scaling behavior
class SMProdAutoScalingStack(Stack):

    def __init__(self, scope: Construct, id: str, project_name: str, autoscaling_config: dict, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Import endpoint name from previous stack
        endpoint_name = Fn.import_value(f"{project_name}-prod-endpoint-name")

        # Auto Scaling Target
        scaling_target = autoscaling.CfnScalableTarget(
            self,
            "EndpointScalingTarget",
            max_capacity=autoscaling_config["autoscaling_max"],
            min_capacity=autoscaling_config["autoscaling_min"],
            resource_id=f"endpoint/{endpoint_name}/variant/AllTraffic",
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            service_namespace="sagemaker",
        )

        # Invocation-based Scaling Policy
        scaling_policy = autoscaling.CfnScalingPolicy(
            self,
            "EndpointInvocationScalingPolicy",
            policy_name="SageMakerVariantInvocationsPerInstance",
            policy_type=autoscaling_config["policy_type"],
            resource_id=f"endpoint/{endpoint_name}/variant/AllTraffic",
            scalable_dimension="sagemaker:variant:DesiredInstanceCount",
            service_namespace="sagemaker",
            target_tracking_scaling_policy_configuration=autoscaling.CfnScalingPolicy.TargetTrackingScalingPolicyConfigurationProperty(
                target_value=autoscaling_config["target_invocations_per_instance"],
                predefined_metric_specification=autoscaling.CfnScalingPolicy.PredefinedMetricSpecificationProperty(
                    predefined_metric_type="SageMakerVariantInvocationsPerInstance"
                ),
                scale_in_cooldown=autoscaling_config["scale_in_cooldown"],
                scale_out_cooldown=autoscaling_config["scale_out_cooldown"],
            ),
        )

        # Ensure scaling policy is created after the scalable target
        scaling_policy.add_dependency(scaling_target)


# Alternative CPU-based Scaling Policy


# from aws_cdk import (
#     Stack,
#     aws_applicationautoscaling as autoscaling,
#     aws_cloudwatch as cloudwatch,
#     Duration,
#     Fn,
# )
# from constructs import Construct


# class SMProdAutoScalingStack(Stack):

#     def __init__(self, scope: Construct, id: str, project_name: str, **kwargs) -> None:
#         super().__init__(scope, id, **kwargs)

#         # Import endpoint name from previous stack
#         endpoint_name = Fn.import_value(f"{project_name}-prod-endpoint-name")

#         # Auto Scaling
#         scaling_target = autoscaling.ScalableTarget(
#             self,
#             "EndpointScalingTarget",
#             service_namespace=autoscaling.ServiceNamespace.SAGEMAKER,
#             scalable_dimension="sagemaker:variant:DesiredInstanceCount",
#             resource_id=f"endpoint/{endpoint_name}/variant/AllTraffic",
#             min_capacity=1,
#             max_capacity=5,
#         )

#         # CPU scaling
#         scaling_target.scale_on_metric(
#             "CPUScaling",
#             metric=cloudwatch.Metric(
#                 metric_name="CPUUtilization",
#                 namespace="AWS/SageMaker",
#                 dimensions_map={
#                     "EndpointName": endpoint_name,
#                     "VariantName": "AllTraffic",
#                 },
#                 statistic="Average",
#                 period=Duration.minutes(1),
#             ),
#             scaling_steps=[
#                 autoscaling.ScalingInterval(upper=30, change=-1),
#                 autoscaling.ScalingInterval(lower=70, change=+1),
#             ],
#             adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
#             cooldown=Duration.minutes(5),
#         )
