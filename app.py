
#!/usr/bin/env python3
import aws_cdk as cdk
from infrastructure.cdk_pipeline_stack import CDKPipelineStack

app = cdk.App()

# Environment
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-central-1"
)

# Stack'i sadece CDK parametreleriyle oluştur
CDKPipelineStack(app, "CDKPipelineStack", env=env)

app.synth()


# aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# Stack silme işleminin event'lerini gerçek zamanlı olarak izlemek için

# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-ec2
# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-kinesis
# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-glue
# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-s3
# aws cloudformation delete-stack --stack-name CDKToolkit


