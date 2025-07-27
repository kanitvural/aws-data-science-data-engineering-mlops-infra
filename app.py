
#!/usr/bin/env python3
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



# import aws_cdk as cdk

# from data_science.cdk_pipeline.cdk_data_science_pipeline import CDKDataSciencePipelineStack


# app = cdk.App()

# # Environment
# env = cdk.Environment(
#     account=app.node.try_get_context("account"),
#     region=app.node.try_get_context("region") or "eu-central-1",
# )

# # Stack'i sadece CDK parametreleriyle oluştur

# CDKDataSciencePipelineStack(app, id="CDKDataSciencePipelineStack", env=env)


# app.synth()

# Stack'i sadece CDK parametreleriyle oluştur
# CDKDEPipelineStack(app, "CDKPipelineStack", env=env)


# aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# Stack silme işleminin event'lerini gerçek zamanlı olarak izlemek için

# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-ec2
# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-kinesis
# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-glue
# aws cloudformation delete-stack --stack-name DataEngineeringStage-data-engineering-s3
# aws cloudformation delete-stack --stack-name CDKToolkit
