
#!/usr/bin/env python3
import aws_cdk as cdk
from infra_pipeline.infra_pipeline_stack import InfraPipelineStack

app = cdk.App()

# Environment
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1"
)

# Stack'i sadece CDK parametreleriyle oluştur
InfraPipelineStack(app, "InfraPipelineStack", env=env)

app.synth()


# aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# aws cloudformation delete-stack --stack-name STACK_NAME