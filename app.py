#!/usr/bin/env python3
import aws_cdk as cdk
from data_engineering.stacks.s3_stack import S3Stack
from data_engineering.stacks.kinesis_stack import KinesisStack
from data_engineering.stacks.glue_stack import GlueStack
from data_engineering.stacks.ec2_stack import EC2Stack

app = cdk.App()

# Environment
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1"
)

# Project prefix
project_name = "data-engineering"

# S3 Stack (önce bu)
s3_stack = S3Stack(
    app, 
    f"{project_name}-s3",
    project_name=project_name,
    env=env
)

# Kinesis Stack
kinesis_stack = KinesisStack(
    app,
    f"{project_name}-kinesis",
    project_name=project_name,
    data_bucket=s3_stack.data_bucket,
    env=env
)

# Glue Stack
glue_stack = GlueStack(
    app,
    f"{project_name}-glue",
    project_name=project_name,
    data_bucket=s3_stack.data_bucket,
    artifacts_bucket=s3_stack.artifacts_bucket,
    notification_email=app.node.try_get_context("notification_email"),
    env=env
)

# EC2 Stack
ec2_stack = EC2Stack(
    app,
    f"{project_name}-ec2",
    project_name=project_name,
    kinesis_stream=kinesis_stack.kinesis_stream,
    env=env
)

# Dependencies
kinesis_stack.add_dependency(s3_stack)
glue_stack.add_dependency(s3_stack)
ec2_stack.add_dependency(kinesis_stack)

app.synth()