#!/usr/bin/env python3

import aws_cdk as cdk

from mlops.cdk_pipeline.cdk_mlops_pipeline import CDKMLOpsPipelineStack

app = cdk.App()


env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1",
)