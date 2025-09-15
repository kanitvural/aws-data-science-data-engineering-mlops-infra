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

        data_bucket_name = Fn.import_value("DataScienceBucketName")
        data_bucket_prefix = "sagemaker-preprocess-output/drift"
        data_bucket_key = "raw_test_data_for_model_drift.csv"
        dynamodb_table_name = Fn.import_value(f"{project_name}-raw-flights-table-name")
        raw_kinesis_stream_name = Fn.import_value(f"{project_name}-KinesisRawName")
        website_url = Fn.import_value("ProjectAppWebsiteURL")
        sns_topic_arn = Fn.import_value(f"{project_name}-sns-topic-arn")
        
        # vpc_id = Fn.import_value("flight-project-vpc-id")

        # public_subnet_ids = [
        #     Fn.import_value("flight-project-subnet-a"),  # eu-central-1a
        #     Fn.import_value("flight-project-subnet-b"),  # eu-central-1b
        #     Fn.import_value("flight-project-subnet-c")   # eu-central-1c
        # ]


        vpc_id = "vpc-05e81295194e18eca"
        public_subnet_ids = [
            "subnet-0f34d5f46cb85310a",
            "subnet-0d2cdff5d7abe1e8d",
            "subnet-025f78bace1dd224f"
        ]
        
        vpc = ec2.Vpc.from_vpc_attributes(
            self,
            "ImportedVPC",
            vpc_id=vpc_id,
            availability_zones=["eu-central-1a", "eu-central-1b", "eu-central-1c"],
            public_subnet_ids=public_subnet_ids
        )

        # Security Group
        security_group = ec2.SecurityGroup(
            self,
            security_group_name=f"{project_name}-data-simulator-sg",
            id="DataSimulatorSG",
            vpc=vpc,
            description="Security group for EC2 data simulator",
            allow_all_outbound=True,
        )

        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(22),
            description="SSH access",
        )

        # IAM Role for EC2
        ec2_role = iam.Role(
            self,
            id="DataSimulatorRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonKinesisFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDynamoDBFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSNSFullAccess"),
            ],
        )

        # User Data Script
        user_data_script = f"""#!/bin/bash
sudo dnf update -y
sudo dnf install -y python3 python3-pip git wget unzip
sudo dnf remove -y awscli || true

cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
sudo ./aws/install --update

sudo ln -sf /usr/local/aws-cli/v2/current/bin/aws /usr/bin/aws

pip3 install --upgrade pip
pip3 install pandas numpy boto3 requests uuid

sudo mkdir -p /opt/data-simulator
sudo chown ec2-user:ec2-user /opt/data-simulator
cd /opt/data-simulator

aws s3 cp s3://{data_bucket_name}/{data_bucket_prefix}/{data_bucket_key} .

cat > data_simulator.py << EOF
import pandas as pd
import json
import sys
import boto3
import numpy as np
from datetime import datetime
import time
import uuid
import logging
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DataSimulator:
    def __init__(self, kinesis_stream_name, dynamodb_table_name, csv_path, sns_topic_arn, website_url):
        self.kinesis_client = boto3.client('kinesis', region_name='eu-central-1')
        self.stream_name = kinesis_stream_name
        self.dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
        self.raw_table = self.dynamodb.Table(dynamodb_table_name)
        self.df = pd.read_csv(csv_path)
        self.current_index = 0
        self.sns_client = boto3.client("sns", region_name="eu-central-1")
        self.sns_topic_arn = sns_topic_arn
        self.website_url = website_url

    def notify_start(self):
        message = "🚀 Data Generator has started streaming!\\n\\nProject app live here: " + self.website_url
        try:
            self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Subject="Data Simulator Started",
                Message=message
            )
            logger.info("SNS notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending SNS notification: {{e}}")

    def generate_flight_event(self, row):
        return {{
            "id": str(uuid.uuid4()),
            "year": int(row['year']),
            "month": int(row['month']),
            "day": int(row['day']),
            "dep_time": str(row['dep_time']) if pd.notna(row['dep_time']) else None,
            "sched_dep_time": str(row['sched_dep_time']) if pd.notna(row['sched_dep_time']) else None,
            "arr_time": str(row['arr_time']) if pd.notna(row['arr_time']) else None,
            "sched_arr_time": str(row['sched_arr_time']) if pd.notna(row['sched_arr_time']) else None,
            "arr_delay": float(row['arr_delay']) if pd.notna(row['arr_delay']) else None,
            "carrier": str(row['carrier']),
            "flight": int(row['flight']),
            "tailnum": str(row['tailnum']) if pd.notna(row['tailnum']) else None,
            "origin": str(row['origin']),
            "dest": str(row['dest']),
            "air_time": float(row['air_time']) if pd.notna(row['air_time']) else None,
            "distance": float(row['distance']) if pd.notna(row['distance']) else None,
            "hour": int(row['hour']),
            "minute": int(row['minute']),
            "airline": str(row['airline']),
            "route": str(row['route']),
            "temp": float(row['temp']) if pd.notna(row['temp']) else None,
            "dewp": float(row['dewp']) if pd.notna(row['dewp']) else None,
            "humid": float(row['humid']) if pd.notna(row['humid']) else None,
            "wind_dir": float(row['wind_dir']) if pd.notna(row['wind_dir']) else None,
            "wind_speed": float(row['wind_speed']) if pd.notna(row['wind_speed']) else None,
            "wind_gust": float(row['wind_gust']) if pd.notna(row['wind_gust']) else None,
            "precip": float(row['precip']) if pd.notna(row['precip']) else None,
            "pressure": float(row['pressure']) if pd.notna(row['pressure']) else None,
            "visib": float(row['visib']) if pd.notna(row['visib']) else None,
            "date": str(row['date']) if pd.notna(row['date']) else None,
            "date_string": str(row['date_string']) if pd.notna(row['date_string']) else None,
            "dep_delay": None,
            "timestamp": str(datetime.utcnow())
        }}

    def send_to_kinesis(self, event):
        try:
            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(event),
                PartitionKey=str(event['flight'])
            )
            logger.info(f"Sent record to Kinesis with flight {{event['flight']}}")
            return response
        except Exception as e:
            logger.error(f"Error sending to Kinesis: {{e}}")
            return None

    def write_to_dynamodb(self, event):
        try:
            event_copy = event.copy()
            for k, v in event_copy.items():
                if isinstance(v, float):
                    event_copy[k] = Decimal(str(v))
            self.raw_table.put_item(Item=event_copy)
            logger.info(f"Wrote record to DynamoDB with id {{event_copy['id']}}")
        except Exception as e:
            logger.error(f"Error writing to DynamoDB: {{e}}")

    def start_streaming(self, events_per_second=10):
        logger.info(f"Streaming to {{self.stream_name}} at {{events_per_second}} events/sec")
        self.notify_start()
        total = len(self.df)
        while self.current_index < total:
            start_time = time.time()
            row = self.df.iloc[self.current_index]
            event = self.generate_flight_event(row)
            self.send_to_kinesis(event)
            self.write_to_dynamodb(event)
            self.current_index += 1
            logger.info(f"Sent event {{self.current_index}} of {{total}}")
            elapsed = time.time() - start_time
            sleep_time = max(0, 1.0 / events_per_second - elapsed)
            time.sleep(sleep_time)

if __name__ == "__main__":
    simulator = DataSimulator(
        "{raw_kinesis_stream_name}",
        "{dynamodb_table_name}",
        "{data_bucket_key}",
        "{sns_topic_arn}",
        "{website_url}"
    )
    simulator.start_streaming(events_per_second=10)
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

        CfnOutput(
            self,
            "EC2InstanceId",
            value=self.ec2_instance.instance_id,
            export_name=f"{project_name}-EC2InstanceId",
        )
        CfnOutput(
            self,
            "EC2PublicIP",
            value=self.ec2_instance.instance_public_ip,
            export_name=f"{project_name}-EC2PublicIP",
        )
        CfnOutput(
            self,
            "EC2PrivateIP",
            value=self.ec2_instance.instance_private_ip,
            export_name=f"{project_name}-EC2PrivateIP",
        )
