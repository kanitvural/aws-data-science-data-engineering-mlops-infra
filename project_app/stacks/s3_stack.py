from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput,
    Duration
)
from constructs import Construct

class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # ----------------------------------------------------------------------
        # Private S3 Bucket
        # ----------------------------------------------------------------------
        bucket = s3.Bucket(
            self,
            "ProjectAppBucket",
            bucket_name=f"{project_name}-bucket-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )
        
        # ----------------------------------------------------------------------
        # Origin Access Control (OAC) - AWS recommended modern approach
        # ----------------------------------------------------------------------
        oac = cloudfront.CfnOriginAccessControl(
            self,
            "OAC",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name=f"{project_name}-OAC",
                origin_access_control_origin_type="s3",
                signing_behavior="always",
                signing_protocol="sigv4"
            )
        )
        
        # ----------------------------------------------------------------------
        # CloudFront Distribution
        # ----------------------------------------------------------------------
        distribution = cloudfront.Distribution(
            self,
            "ProjectAppDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100
        )
        
        # ----------------------------------------------------------------------
        # CRITICAL: Attach OAC to CloudFront Distribution (L1 override)
        # ----------------------------------------------------------------------
        cfn_distribution = distribution.node.default_child
        cfn_distribution.add_property_override(
            "DistributionConfig.Origins.0.OriginAccessControlId",
            oac.attr_id
        )
        
        # ----------------------------------------------------------------------
        # Bucket Policy - Grant CloudFront access via OAC
        # ----------------------------------------------------------------------
        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[f"{bucket.bucket_arn}/*"],
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{self.account}:distribution/{distribution.distribution_id}"
                    }
                }
            )
        )
        
        # ----------------------------------------------------------------------
        # Outputs
        # ----------------------------------------------------------------------
        CfnOutput(
            self,
            "S3BucketName",
            value=bucket.bucket_name,
            description="S3 Bucket name for ProjectApp Frontend",
            export_name="ProjectAppBucketName",
        )
        
        CfnOutput(
            self,
            "CloudFrontURL",
            value=f"https://{distribution.distribution_domain_name}",
            description="CloudFront URL for frontend",
            export_name="ProjectAppCloudFrontURL",
        )