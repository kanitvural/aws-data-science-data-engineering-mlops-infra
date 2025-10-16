from aws_cdk import (
    Duration,
    Stack,
    aws_redshiftserverless as redshift_serverless,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    custom_resources as cr,
    CfnOutput,
    RemovalPolicy,
    Fn,
    CustomResource,
)
from constructs import Construct


class RedshiftStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        project_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)
        
        data_bucket_name = Fn.import_value("DataLakeBucketName")
        glue_database_name = Fn.import_value("GlueDatabaseName")
        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")         

        # Import existing VPC and subnets from EC2 stack
        vpc_id = Fn.import_value("flight-project-vpc-id")

        public_subnet_ids = [
            Fn.import_value("flight-project-subnet-a"),
            Fn.import_value("flight-project-subnet-b"),
            Fn.import_value("flight-project-subnet-c"),
        ]

        vpc = ec2.Vpc.from_vpc_attributes(
            self,
            "ImportedVPC",
            vpc_id=vpc_id,
            availability_zones=["eu-central-1a", "eu-central-1b", "eu-central-1c"],
            public_subnet_ids=public_subnet_ids,
        )

        # Security Group for Redshift Serverless
        redshift_sg = ec2.SecurityGroup(
            self,
            "RedshiftServerlessSG",
            vpc=vpc,
            security_group_name=f"{project_name}-redshift-serverless-sg",
            description="Security group for Redshift Serverless",
            allow_all_outbound=True
        )

        # Allow inbound on port 5439 from anywhere
        # TODO: Restrict to your IP via context or manually after deployment
        redshift_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5439),
            description="Allow Redshift access (restrict to your IP in production)"
        )

        # ✅ Secrets Manager - Generate random password
        db_secret = secretsmanager.Secret(
            self,
            "RedshiftAdminSecret",
            secret_name=f"{project_name}/redshift/admin-credentials",
            description="Redshift Serverless admin credentials",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username":"admin"}',
                generate_string_key="password",
                exclude_punctuation=True,  # Redshift doesn't like some special chars
                include_space=False,
                password_length=32,
                require_each_included_type=True
            ),
            removal_policy=RemovalPolicy.DESTROY
        )

        # IAM Role for Redshift Serverless
        redshift_role = iam.Role(
            self,
            "RedshiftServerlessRole",
            assumed_by=iam.ServicePrincipal("redshift.amazonaws.com"),
            description="IAM role for Redshift Serverless to access Glue Catalog and S3"
        )

        # Add Glue Catalog access
        redshift_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "glue:GetDatabase",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartition",
                    "glue:GetPartitions",
                    "glue:BatchGetPartition"
                ],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:catalog",
                    f"arn:aws:glue:{self.region}:{self.account}:database/{glue_database_name}",
                    f"arn:aws:glue:{self.region}:{self.account}:table/{glue_database_name}/*"
                ]
            )
        )

        # Add S3 read access for Spectrum
        redshift_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation"
                ],
                resources=[
                    f"arn:aws:s3:::{data_bucket_name}",
                    f"arn:aws:s3:::{data_bucket_name}/*"
                ]
            )
        )

        # Redshift Serverless Namespace
        namespace = redshift_serverless.CfnNamespace(
            self,
            "RedshiftNamespace",
            namespace_name=f"{project_name}-namespace",
            admin_username="admin",
            admin_user_password=db_secret.secret_value_from_json("password").unsafe_unwrap(),  # ✅ From Secrets Manager
            db_name="flightdb",
            iam_roles=[redshift_role.role_arn],
            default_iam_role_arn=redshift_role.role_arn,
            log_exports=["userlog", "connectionlog", "useractivitylog"],
            manage_admin_password=False  # We manage it via Secrets Manager
        )
        
        namespace.apply_removal_policy(RemovalPolicy.DESTROY)

        # Redshift Serverless Workgroup
        workgroup = redshift_serverless.CfnWorkgroup(
            self,
            "RedshiftWorkgroup",
            workgroup_name=f"{project_name}-workgroup",
            namespace_name=namespace.namespace_name,
            base_capacity=8,  # 8 RPU as requested
            publicly_accessible=True,  # Public endpoint for PowerBI
            subnet_ids=public_subnet_ids,
            security_group_ids=[redshift_sg.security_group_id],
            enhanced_vpc_routing=False
        )
        
        workgroup.add_dependency(namespace)
        workgroup.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda Role for Spectrum setup
        spectrum_lambda_role = iam.Role(
            self,
            "SpectrumSetupLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole")
            ]
        )

        # Add Redshift Data API permissions
        spectrum_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "redshift-serverless:GetCredentials",
                    "redshift-data:ExecuteStatement",
                    "redshift-data:DescribeStatement",
                    "redshift-data:GetStatementResult"
                ],
                resources=["*"]
            )
        )

        # Add Secrets Manager read permission for Lambda
        db_secret.grant_read(spectrum_lambda_role)

        # Add SNS publish permission for Lambda
        spectrum_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:Publish"],
                resources=[sns_topic_arn]
            )
        )

        # Lambda function to setup Spectrum external schema
        spectrum_setup_lambda = lambda_.Function(
            self,
            "SpectrumSetupLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("data_engineering/lambda_funcs/setup_redshift_spectrum"),
            environment={
                "WORKGROUP_NAME": workgroup.workgroup_name,
                "DATABASE_NAME": "flightdb",
                "GLUE_DATABASE": glue_database_name,
                "IAM_ROLE_ARN": redshift_role.role_arn,
                "SECRET_ARN": db_secret.secret_arn,
                "SNS_TOPIC_ARN": sns_topic_arn,  
                "REDSHIFT_ENDPOINT": workgroup.attr_workgroup_endpoint_address,
                "REGION": self.region
            },
            role=spectrum_lambda_role,
            timeout=Duration.minutes(5),
            memory_size=256
        )

        # CloudWatch Log Group for Lambda
        logs.LogGroup(
            self,
            "SpectrumSetupLambdaLogGroup",
            log_group_name=f"/aws/lambda/{spectrum_setup_lambda.function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Custom Resource to trigger Lambda after Redshift is ready
        spectrum_provider = cr.Provider(
            self,
            "SpectrumSetupProvider",
            on_event_handler=spectrum_setup_lambda
        )

        spectrum_custom_resource = CustomResource(
            self,
            "SpectrumSetupCustomResource",
            service_token=spectrum_provider.service_token,
            properties={
                "WorkgroupName": workgroup.workgroup_name,
                "Timestamp": str(self.node.try_get_context("timestamp") or "initial")
            }
        )

        spectrum_custom_resource.node.add_dependency(workgroup)

        # Outputs
        CfnOutput(
            self,
            "RedshiftNamespaceName",
            value=namespace.namespace_name,
            description="Redshift Serverless Namespace Name",
            export_name=f"{project_name}-redshift-namespace"
        )

        CfnOutput(
            self,
            "RedshiftWorkgroupName",
            value=workgroup.workgroup_name,
            description="Redshift Serverless Workgroup Name",
            export_name=f"{project_name}-redshift-workgroup"
        )

        CfnOutput(
            self,
            "RedshiftEndpoint",
            value=workgroup.attr_workgroup_endpoint_address,
            description="Redshift Serverless Endpoint (for PowerBI connection)",
            export_name=f"{project_name}-redshift-endpoint"
        )

        CfnOutput(
            self,
            "RedshiftPort",
            value="5439",
            description="Redshift Serverless Port"
        )

        CfnOutput(
            self,
            "RedshiftDatabaseName",
            value="flightdb",
            description="Redshift Database Name"
        )

        CfnOutput(
            self,
            "RedshiftSecretArn",
            value=db_secret.secret_arn,
            description="Secrets Manager ARN for Redshift credentials"
        )

        CfnOutput(
            self,
            "RedshiftUsername",
            value="admin",
            description="Redshift Admin Username"
        )

        CfnOutput(
            self,
            "RedshiftIAMRoleArn",
            value=redshift_role.role_arn,
            description="Redshift IAM Role ARN for Spectrum"
        )

        CfnOutput(
            self,
            "SpectrumSchemaName",
            value="spectrum",
            description="External schema name for Spectrum queries"
        )

        CfnOutput(
            self,
            "GetPasswordCommand",
            value=f"aws secretsmanager get-secret-value --secret-id {db_secret.secret_name} --query SecretString --output text | jq -r .password",
            description="AWS CLI command to retrieve Redshift password"
        )

        CfnOutput(
            self,
            "PowerBIConnectionString",
            value=f"Host={workgroup.attr_workgroup_endpoint_address};Port=5439;Database=flightdb;UID=admin",
            description="PowerBI connection string (get password from Secrets Manager)"
        )