import aws_cdk as cdk
from multi_agent_llm.cdk_pipeline.cdk_multi_agent_llm_pipeline import CDKLLMPipelineStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1",
)

CDKLLMPipelineStack(app, "CDKLLMPipelineStack", env=env)

app.synth()