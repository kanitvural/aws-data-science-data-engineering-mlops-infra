from aws_cdk import (
    Stack,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    CfnOutput
 
)
from constructs import Construct


class SNSStack(Stack):
    def __init__(self, scope: Construct, id: str,project_name: str, notification_email: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.topic = sns.Topic(
            self, "ProjectAppNotificationTopic",
            display_name="Project App Notifications",
        )

        self.topic.add_subscription(subs.EmailSubscription(notification_email))
        
        CfnOutput(
            self, "SNSNotificationTopicArn",
            value=self.topic.topic_arn,
            export_name=f"{project_name}-sns-topic-arn"
        )

