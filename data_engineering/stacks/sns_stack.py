from aws_cdk import (
    Stack,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct


class SNSStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, notification_email: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.topic = sns.Topic(
            self, "DataEngineeringJobNotificationTopic",
            display_name="Data Engineering Job Notifications",
        )

        self.topic.add_subscription(subs.EmailSubscription(notification_email))
        
        self.topic.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowEventBridgeToPublish",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("events.amazonaws.com")],
                actions=["sns:Publish"],
                resources=[self.topic.topic_arn],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": self.account
                    }
                }
            )
        )
        
        CfnOutput(
            self, "SNSNotificationTopicArn",
            value=self.topic.topic_arn,
            export_name=f"{project_name}-sns-topic-arn"
        )
