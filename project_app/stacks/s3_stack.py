from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ----------------------------------------------------------------------
        # Private S3 Bucket (static website hosting)
        # ----------------------------------------------------------------------
        bucket = s3.Bucket(
            self,
            "ProjectAppBucket",
            bucket_name=f"{project_name}-bucket-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            website_index_document="index.html",
            website_error_document="error.html"
        )

        # ----------------------------------------------------------------------
        # CloudFront Distribution
        # ----------------------------------------------------------------------
        oai = cloudfront.OriginAccessIdentity(
            self,
            "CloudFrontOAI",
            comment="OAI for private S3 access"
        )

        bucket.grant_read(oai)

        distribution = cloudfront.Distribution(
            self,
            "ProjectAppDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(bucket, origin_access_identity=oai),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            ),
            price_class=cloudfront.PriceClass.PRICE_CLASS_100  # NA & EU
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
