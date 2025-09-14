import aws_cdk as cdk
from data_engineering.cdk_pipeline.cdk_data_engineering_pipeline import CDKDataEngineeringPipelineStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1",
)

CDKDataEngineeringPipelineStack(app, "CDKDataEngineeringPipelineStack", env=env)

app.synth()