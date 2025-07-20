#!/usr/bin/env python3
import aws_cdk as cdk
from infra_pipeline.infra_pipeline_stack import InfraPipelineStack

app = cdk.App()

# Environment
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1"
)

# Project prefix
project_name = app.node.try_get_context("project_name") or "data-engineering"
notification_email = app.node.try_get_context("notification_email")

InfraPipelineStack(
    app, 
    "InfraPipelineStack", 
    env=env,
    project_name=project_name,
    notification_email=notification_email
)

app.synth()