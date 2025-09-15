import aws_cdk as cdk
from project_app.cdk_pipeline.cdk_app_pipeline import CDKProjectAppPipelineStack

app = cdk.App()

# Environment
env = cdk.Environment(
    account=app.node.try_get_context("account") or "058264126563",
    region=app.node.try_get_context("region") or "eu-central-1",
)

# Stack'i sadece CDK parametreleriyle oluştur
CDKProjectAppPipelineStack(app, "CDKProjectAppPipelineStack", env=env)

app.synth()