import aws_cdk as core
import aws_cdk.assertions as assertions

from aws_data_science_data_engineering_mlops_infra.aws_data_science_data_engineering_mlops_infra_stack import AwsDataScienceDataEngineeringMlopsInfraStack

# example tests. To run these tests, uncomment this file along with the example
# resource in aws_data_science_data_engineering_mlops_infra/aws_data_science_data_engineering_mlops_infra_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AwsDataScienceDataEngineeringMlopsInfraStack(app, "aws-data-science-data-engineering-mlops-infra")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
