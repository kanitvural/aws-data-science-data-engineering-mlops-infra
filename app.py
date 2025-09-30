import aws_cdk as cdk
from project_app.cdk_pipeline.cdk_app_pipeline import CDKAppPipelineStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1",
)

CDKAppPipelineStack(app, "CDKLLMPipelineStack", env=env)

app.synth()