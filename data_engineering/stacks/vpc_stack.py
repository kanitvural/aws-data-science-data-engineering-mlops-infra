from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput,
    Fn,
)
from constructs import Construct


class VPCStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # ✅ Custom VPC (10.0.0.0/16 with 3 public subnets matching the image)
        vpc = ec2.Vpc(
            self,
            id="FlightProjectVPC",
            vpc_name="flight-project-vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            availability_zones=["eu-central-1a", "eu-central-1b", "eu-central-1c"],
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
            nat_gateways=0,
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # ✅ S3 VPC Endpoint (Gateway endpoint)
        vpc.add_gateway_endpoint(
            id="S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)],
        )

        # VPC ID and Subnet IDs export
        CfnOutput(
            self,
            "VPCId",
            value=vpc.vpc_id,
            export_name="flight-project-vpc-id",
        )

        CfnOutput(
            self,
            "PublicSubnetA",
            value=vpc.public_subnets[0].subnet_id,
            export_name="flight-project-subnet-a",
        )

        CfnOutput(
            self,
            "PublicSubnetB",
            value=vpc.public_subnets[1].subnet_id,
            export_name="flight-project-subnet-b",
        )

        CfnOutput(
            self,
            "PublicSubnetC",
            value=vpc.public_subnets[2].subnet_id,
            export_name="flight-project-subnet-c",
        )
