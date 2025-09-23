from aws_cdk import (
    Stack,
    Duration,
    Fn,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_lambda_event_sources as event_sources,
    aws_dynamodb as dynamodb,
    CfnOutput,
)
from constructs import Construct


class LambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ----------------------------------------------------------------------
        # Import Kinesis Streams
        # ----------------------------------------------------------------------
        kinesis_raw_arn = Fn.import_value(f"{project_name}-KinesisRawArn")
        kinesis_processed_arn = Fn.import_value(f"{project_name}-KinesisProcessedArn")
        kinesis_predicted_arn = Fn.import_value(f"{project_name}-KinesisPredictedArn")

        kinesis_raw = kinesis.Stream.from_stream_arn(self, "RawStream", kinesis_raw_arn)
        kinesis_processed = kinesis.Stream.from_stream_arn(self, "ProcessedStream", kinesis_processed_arn)
        kinesis_predicted = kinesis.Stream.from_stream_arn(self, "PredictedStream", kinesis_predicted_arn)

        # ----------------------------------------------------------------------
        # Import DynamoDB Table
        # ----------------------------------------------------------------------
        raw_flights_table_name = Fn.import_value(f"{project_name}-raw-flights-table-name")
        raw_flights_table = dynamodb.Table.from_table_name(
            self, "RawFlightsTable", raw_flights_table_name
        )
        
        websocket_table_name = Fn.import_value(f"{project_name}-websocket-connections-table-name")
        websocket_table = dynamodb.Table.from_table_name(
            self, "WebsocketConnectionsTable", websocket_table_name
        )

        # ----------------------------------------------------------------------
        # Import Endpoint Name
        # ----------------------------------------------------------------------

        # prod_endpoint_name = Fn.import_value("mlops-prod-endpoint-name") test
        prod_endpoint_name = "mlops-prod-endpoint"

        # ----------------------------------------------------------------------
        # Lambda Roles
        # ----------------------------------------------------------------------
        preprocess_lambda_role = iam.Role(
            self,
            "PreprocessLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        preprocess_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kinesis:PutRecord",
                    "kinesis:PutRecords",
                ],
                resources=[kinesis_processed_arn],
            )
        )

        inference_lambda_role = iam.Role(
            self,
            "InferenceLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        inference_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kinesis:PutRecord",
                    "kinesis:PutRecords",
                ],
                resources=[kinesis_predicted_arn],
            )
        )

        inference_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:InvokeEndpoint",
                ],
                resources=["*"],
            )
        )

        writer_lambda_role = iam.Role(
            self,
            "WriterLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        writer_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:UpdateItem",
                ],
                resources=[raw_flights_table.table_arn],
            )
        )
        
        flight_stream_handler_lambda_role = iam.Role(
            self,
            "FlightStreamHandlerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
        )
        flight_stream_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",   
                    "dynamodb:UpdateItem"
                ],
                resources=[websocket_table.table_arn],
            )
        )
        flight_stream_handler_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=["*"],
            )
        )

        # ----------------------------------------------------------------------
        # Lambda Functions
        # ----------------------------------------------------------------------
        pre_pandas_layer = lambda_.LayerVersion(
            self,
            "PandasLayerPre",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/preprocess_lambda/lambda_layer/lambda_layer.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            description="Layer with pandas for preprocess lambda",
        )

        preprocess_lambda = lambda_.Function(
            self,
            "PreprocessLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/preprocess_lambda"),
            role=preprocess_lambda_role,
            layers=[pre_pandas_layer],
            environment={
                "REGION": self.region,
                "KINESIS_PROCESSED_STREAM_NAME": kinesis_processed.stream_name,
            },
            timeout=Duration.seconds(60),
        )
        preprocess_lambda.add_event_source(
            event_sources.KinesisEventSource(
                kinesis_raw,
                batch_size=10,
                starting_position=lambda_.StartingPosition.TRIM_HORIZON,
            )
        )

        inf_pandas_layer = lambda_.LayerVersion(
            self,
            "PandasLayerInf",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/inference_lambda/lambda_layer/lambda_layer.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            description="Layer with pandas for preprocess lambda",
        )

        inference_lambda = lambda_.Function(
            self,
            "InferenceLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/inference_lambda"),
            role=inference_lambda_role,
            layers=[inf_pandas_layer],
            environment={
                "REGION": self.region,
                "ENDPOINT_NAME": prod_endpoint_name,
                "KINESIS_PREDICTED_STREAM_NAME": kinesis_predicted.stream_name,
            },
            timeout=Duration.seconds(60),
        )
        inference_lambda.add_event_source(
            event_sources.KinesisEventSource(
                kinesis_processed, batch_size=10, starting_position=lambda_.StartingPosition.TRIM_HORIZON
            )
        )

        writer_lambda = lambda_.Function(
            self,
            "WriterLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/writer_lambda"),
            role=writer_lambda_role,
            environment={
                "REGION": self.region,
                "TABLE_NAME": raw_flights_table.table_name,
            },
            timeout=Duration.seconds(60),
        )
        writer_lambda.add_event_source(
            event_sources.KinesisEventSource(
                kinesis_predicted, batch_size=10, starting_position=lambda_.StartingPosition.TRIM_HORIZON
            )
        )
        
        api_gateway_websocket_endpoint = Fn.import_value(f"{project_name}-FlightsWebSocketEndpoint")

        flight_stream_handler_lambda = lambda_.Function(
            self,
            "FlightStreamLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("project_app/lambda_funcs/api_gateway_websocket_lambdas/flight_dynamodb_stream_lambda"),
            role=flight_stream_handler_lambda_role,
            environment={
                "TABLE_NAME": websocket_table.table_name,
                "REGION": self.region,
                "API_GATEWAY_WEBSOCKET_ENDPOINT": api_gateway_websocket_endpoint
            },
        )
        flight_stream_handler_lambda.add_event_source(
            event_sources.DynamoEventSource(
                raw_flights_table,
                starting_position=lambda_.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                report_batch_item_failures=True,
            )
        )

        # ----------------------------------------------------------------------
        # CFN Outputs
        # ----------------------------------------------------------------------

        # Preprocess Lambda
        CfnOutput(
            self,
            "PreprocessLambdaName",
            value=preprocess_lambda.function_name,
            description="Preprocess Lambda function name",
            export_name="PreprocessLambdaName",
        )
        CfnOutput(
            self,
            "PreprocessLambdaArn",
            value=preprocess_lambda.function_arn,
            description="Preprocess Lambda function ARN",
            export_name="PreprocessLambdaArn",
        )

        # Inference Lambda
        CfnOutput(
            self,
            "InferenceLambdaName",
            value=inference_lambda.function_name,
            description="Inference Lambda function name",
            export_name="InferenceLambdaName",
        )
        CfnOutput(
            self,
            "InferenceLambdaArn",
            value=inference_lambda.function_arn,
            description="Inference Lambda function ARN",
            export_name="InferenceLambdaArn",
        )

        # Writer Lambda
        CfnOutput(
            self,
            "WriterLambdaName",
            value=writer_lambda.function_name,
            description="Writer Lambda function name",
            export_name="WriterLambdaName",
        )
        CfnOutput(
            self,
            "WriterLambdaArn",
            value=writer_lambda.function_arn,
            description="Writer Lambda function ARN",
            export_name="WriterLambdaArn",
        )
