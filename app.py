import aws_cdk as cdk
from data_engineering.cdk_pipeline.cdk_data_engineering_pipeline import CDKDataEngineeringPipelineStack

app = cdk.App()

# Environment
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1",
)

# Stack'i sadece CDK parametreleriyle oluştur
CDKDataEngineeringPipelineStack(app, "CDKDataEngineeringPipelineStack", env=env)

app.synth()