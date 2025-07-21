# stacks/ec2_stack.py  

from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_kinesis as kinesis,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct


class EC2Stack(Stack):
    def __init__(self, scope: Construct, construct_id: str, project_name: str, kinesis_stream: kinesis.Stream, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ✅ Custom VPC (10.0.0.0/16 with 3 public subnets matching the image)
        vpc = ec2.Vpc(
            self,
            "DataDepartmentVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            availability_zones=["eu-central-1a", "eu-central-1b", "eu-central-1c"],
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="PublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                )
            ],
            nat_gateways=0,
            enable_dns_hostnames=True,
            enable_dns_support=True
        )
        
        # ✅ S3 VPC Endpoint (Gateway endpoint)
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)]
        )
        

        # ✅ Security Group
        security_group = ec2.SecurityGroup(
            self,
            "DataSimulatorSecurityGroup",
            vpc=vpc,
            description="Security group for EC2 data simulator",
            allow_all_outbound=True
        )

        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(22),
            description="SSH access"
        )

        # ✅ IAM Role for EC2
        ec2_role = iam.Role(
            self,
            "DataSimulatorRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonKinesisFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess")
            ]
        )
        

        # ✅ Amazon Linux 2023 User Data Script
        user_data_script = f"""#!/bin/bash
dnf update -y
dnf install -y python3 python3-pip git wget unzip
dnf remove -y awscli || true

cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
sudo ./aws/install --update

sudo ln -sf /usr/local/aws-cli/v2/current/bin/aws /usr/bin/aws

pip3 install --upgrade pip
pip3 install pandas numpy boto3 requests


mkdir -p /opt/data-simulator
sudo chown ec2-user:ec2-user /opt/data-simulator
cd /opt/data-simulator

aws s3 cp s3://kntbucket/2020-Jan.csv .

cat > data_simulator.py << EOF
import pandas as pd
import json
import boto3
import numpy as np
from datetime import datetime
import time
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataSimulator:
    def __init__(self, kinesis_stream_name, csv_path):
        self.kinesis_client = boto3.client('kinesis',region_name='eu-central-1')
        self.stream_name = kinesis_stream_name
        self.df = pd.read_csv(csv_path)
        self.current_index = 0
        
    def generate_web_log(self, row):
        return {{
            "timestamp": datetime.now().isoformat() + "Z",
            "user_id": str(row['user_id']),
            "session_id": str(row['user_session']),
            "event_type": row['event_type'],
            "product_id": str(row['product_id']),
            "category": row['category_code'] if pd.notna(row['category_code']) else "unknown",
            "brand": row['brand'] if pd.notna(row['brand']) else "unknown",
            "price": float(row['price']) if pd.notna(row['price']) else 0.0,
            "ip_address": f"192.168.{{random.randint(1,255)}}.{{random.randint(1,255)}}",
            "user_agent": "Mozilla/5.0 (compatible; DataSimulator/1.0)",
            "page_url": f"/product/{{row['product_id']}}",
            "referrer": "https://google.com" if random.random() > 0.3 else "direct"
        }}
    
    def send_to_kinesis(self, data):
        try:
            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(data),
                PartitionKey=str(data['user_id'])
            )
            logger.info(f"Kinesis put_record response: {{response}}")
            return response
        except Exception as e:
            logger.error(f"Error sending to Kinesis: {{e}}")
            return None
    
    def start_streaming(self, events_per_second=5):
        logger.info(f"Streaming to {{self.stream_name}} at {{events_per_second}} events/sec")
        while self.current_index < len(self.df):
            row = self.df.iloc[self.current_index]
            event = self.generate_web_log(row)
            self.send_to_kinesis(event)
            logger.info(f"Sent event {{self.current_index + 1}}/{{len(self.df)}}")
            self.current_index += 1
            time.sleep(1.0 / events_per_second)

if __name__ == "__main__":
    stream_name = "{kinesis_stream.stream_name}"
    simulator = DataSimulator(stream_name, "2020-Jan.csv")
    simulator.start_streaming(events_per_second=2)
EOF

chmod +x data_simulator.py

sudo tee /etc/systemd/system/data-simulator.service > /dev/null << 'EOF'
[Unit]
Description=Flights Data Simulator
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/data-simulator
ExecStart=/usr/bin/python3 /opt/data-simulator/data_simulator.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF


sudo systemctl daemon-reload
sudo systemctl enable data-simulator.service
sudo systemctl start data-simulator.service

"""

        key_pair = ec2.KeyPair.from_key_pair_name(
            self,
            "ImportedKeyPair",
            key_pair_name=self.node.try_get_context("key_name")
        )
       
        # ✅ EC2 Instance (Amazon Linux 2023)
        self.ec2_instance = ec2.Instance(
            self,
            "DataSimulatorInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=security_group,
            role=ec2_role,
            user_data=ec2.UserData.custom(user_data_script),
            key_pair=key_pair,
        )
        

        # ✅ Outputs
        CfnOutput(self, "EC2InstanceId", value=self.ec2_instance.instance_id)
        CfnOutput(self, "EC2PublicIP", value=self.ec2_instance.instance_public_ip)
        CfnOutput(self, "EC2PrivateIP", value=self.ec2_instance.instance_private_ip)
