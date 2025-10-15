from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput,
    Fn,
)
from constructs import Construct


class EC2Stack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        project_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        data_bucket_name = Fn.import_value("DataLakeBucketName")
        kinesis_stream_name = Fn.import_value("KinesisStreamName")

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

        # ✅ Security Group
        security_group = ec2.SecurityGroup(
            self,
            security_group_name=f"{project_name}-data-simulator-sg",
            id="DataSimulatorSecurityGroup",
            vpc=vpc,
            description="Security group for EC2 data simulator",
            allow_all_outbound=True,
        )

        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(22), description="SSH access"
        )

        # ✅ IAM Role for EC2
        ec2_role = iam.Role(
            self,
            id="DataSimulatorRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonKinesisFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
            ],
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

aws s3 cp s3://{data_bucket_name}/data/flights_weather2022.csv .

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
        self.kinesis_client = boto3.client('kinesis', region_name='eu-central-1')
        self.stream_name = kinesis_stream_name
        self.df = pd.read_csv(csv_path)
        self.current_index = 0

    def generate_flight_event(self, row):
        return {{
            "year": int(row['year']),
            "month": int(row['month']),
            "day": int(row['day']),
            "dep_time": float(row['dep_time']) if pd.notna(row['dep_time']) else None,
            "sched_dep_time": int(row['sched_dep_time']) if pd.notna(row['sched_dep_time']) else None,
            "dep_delay": float(row['dep_delay']) if pd.notna(row['dep_delay']) else None,
            "arr_time": float(row['arr_time']) if pd.notna(row['arr_time']) else None,
            "sched_arr_time": int(row['sched_arr_time']) if pd.notna(row['sched_arr_time']) else None,
            "arr_delay": float(row['arr_delay']) if pd.notna(row['arr_delay']) else None,
            "carrier": row['carrier'],
            "flight": int(row['flight']),
            "tailnum": str(row['tailnum']) if pd.notna(row['tailnum']) else None,
            "origin": row['origin'],
            "dest": row['dest'],
            "air_time": float(row['air_time']) if pd.notna(row['air_time']) else None,
            "distance": float(row['distance']) if pd.notna(row['distance']) else None,
            "hour": int(row['hour']),
            "minute": int(row['minute']),
            "airline": row['airline'],
            "route": row['route'],
            "temp": float(row['temp']) if pd.notna(row['temp']) else None,
            "dewp": float(row['dewp']) if pd.notna(row['dewp']) else None,
            "humid": float(row['humid']) if pd.notna(row['humid']) else None,
            "wind_dir": float(row['wind_dir']) if pd.notna(row['wind_dir']) else None,
            "wind_speed": float(row['wind_speed']) if pd.notna(row['wind_speed']) else None,
            "wind_gust": float(row['wind_gust']) if pd.notna(row['wind_gust']) else None,
            "precip": float(row['precip']) if pd.notna(row['precip']) else None,
            "pressure": float(row['pressure']) if pd.notna(row['pressure']) else None,
            "visib": float(row['visib']) if pd.notna(row['visib']) else None
        }}

    def send_to_kinesis(self, batch):
        records = [
            {{
                "Data": json.dumps(data),
                "PartitionKey": str(data['flight'])
            }} for data in batch
        ]

        try:
            response = self.kinesis_client.put_records(
                Records=records,
                StreamName=self.stream_name
            )
            failed = response.get("FailedRecordCount", 0)
            if failed > 0:
                logger.warning(f"{{failed}} records failed to send.")
            else:
                logger.info(f"Successfully sent batch of {{len(records)}} records.")
            return response
        except Exception as e:
            logger.error(f"Error sending to Kinesis: {{e}}")
            return None

    def start_streaming(self, events_per_second=5):
        logger.info(f"Streaming to {{self.stream_name}} at {{events_per_second}} events/sec")
        batch_size = events_per_second
        total = len(self.df)

        while self.current_index < total:
            start_time = time.time()

            end_index = min(self.current_index + batch_size, total)
            batch_df = self.df.iloc[self.current_index:end_index]

            batch_events = [self.generate_flight_event(row) for _, row in batch_df.iterrows()]
            self.send_to_kinesis(batch_events)

            logger.info(f"Sent events {{self.current_index + 1}} to {{end_index}} of {{total}}")
            self.current_index = end_index

            elapsed = time.time() - start_time
            sleep_time = max(0, 1.0 - elapsed)
            time.sleep(sleep_time)

if __name__ == "__main__":
    stream_name = "{kinesis_stream_name}"
    simulator = DataSimulator(stream_name, "flights_weather2022.csv")
    simulator.start_streaming(events_per_second=500)
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
            self, "ImportedKeyPair", key_pair_name=self.node.try_get_context("key_name")
        )

        # ✅ EC2 Instance (Amazon Linux 2023)
        self.ec2_instance = ec2.Instance(
            self,
            id="DataSimulatorInstance",
            instance_name=f"{project_name}-data-simulator-ec2",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MEDIUM,
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=security_group,
            role=ec2_role,
            user_data=ec2.UserData.custom(user_data_script),
            key_pair=key_pair,
        )

        # ✅ Outputs
        CfnOutput(
            self,
            "EC2InstanceId",
            value=self.ec2_instance.instance_id,
            export_name="EC2InstanceId",
        )
        CfnOutput(
            self,
            "EC2PublicIP",
            value=self.ec2_instance.instance_public_ip,
            export_name="EC2PublicIP",
        )
        CfnOutput(
            self,
            "EC2PrivateIP",
            value=self.ec2_instance.instance_private_ip,
            export_name="EC2PrivateIP",
        )
        
        # VPC ID and Subnet IDs export
        CfnOutput(
            self,
            "VPCId",
            value=vpc.vpc_id,
            export_name="flight-project-vpc-id"
        )

        CfnOutput(
            self,
            "PublicSubnetA",
            value=vpc.public_subnets[0].subnet_id,
            export_name="flight-project-subnet-a"
        )

        CfnOutput(
            self,
            "PublicSubnetB", 
            value=vpc.public_subnets[1].subnet_id,
            export_name="flight-project-subnet-b"
        )

        CfnOutput(
            self,
            "PublicSubnetC",
            value=vpc.public_subnets[2].subnet_id,
            export_name="flight-project-subnet-c"
        )
