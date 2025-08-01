from aws_cdk import (
    Stack,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_iam as iam,
)
from constructs import Construct


class SNSStack(Stack):
    def __init__(self, scope: Construct, id: str, notification_email: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.topic = sns.Topic(
            self, "SageMakerJobNotificationTopic",
            display_name="SageMaker Job Notifications",
        )

        self.topic.add_subscription(subs.EmailSubscription(notification_email))

       
