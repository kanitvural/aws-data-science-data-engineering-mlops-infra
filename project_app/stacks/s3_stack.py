from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput,
    Duration,
    Fn
)
from constructs import Construct
import json


class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, project_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ----------------------------------------------------------------------
        # S3 Bucket for Static Website Hosting
        # ----------------------------------------------------------------------
        bucket = s3.Bucket(
            self,
            id="ProjectAppBucket",
            bucket_name=f"{project_name}-bucket-{self.account}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            website_index_document="index.html",
            website_error_document="error.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            )
        )

        # ----------------------------------------------------------------------
        # Bucket Policy for Website Hosting
        # ----------------------------------------------------------------------
        bucket_policy = iam.PolicyDocument(
            statements=[
                # Public read access for website content
                iam.PolicyStatement(
                    sid="PublicReadGetObject",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AnyPrincipal()],
                    actions=["s3:GetObject"],
                    resources=[f"{bucket.bucket_arn}/*"]
                ),
                # Bucket owner full access
                iam.PolicyStatement(
                    sid="BucketOwnerFullControl",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AccountRootPrincipal()],
                    actions=[
                        "s3:ListBucket",
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:GetBucketAcl",
                        "s3:PutBucketAcl"
                    ],
                    resources=[
                        bucket.bucket_arn,
                        f"{bucket.bucket_arn}/*"
                    ]
                )
            ]
        )

        # Apply the bucket policy
        s3.CfnBucketPolicy(
            self,
            "BucketPolicy",
            bucket=bucket.bucket_name,
            policy_document=bucket_policy
        )

        # ----------------------------------------------------------------------
        # Frontend Files Deployment
        # ----------------------------------------------------------------------

        frontend_path = "project_app/frontend"
        
        deployment = s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3deploy.Source.asset(frontend_path)],
            destination_bucket=bucket,
            # Cache control headers
            cache_control=[
                s3deploy.CacheControl.max_age(Duration.hours(1)) 
            ],
            content_type="text/html",
            prune=True,
        )

        # Specific cache control for different file types
        static_deployment = s3deploy.BucketDeployment(
            self,
            "DeployStaticAssets",
            sources=[s3deploy.Source.asset(frontend_path)],
            destination_bucket=bucket,
            cache_control=[
                s3deploy.CacheControl.max_age(Duration.days(365))  
            ],
            exclude=["*.html"], 
            include=["*.css", "*.js", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.ico"],
            prune=False, 
        )
        
        static_deployment.node.add_dependency(deployment)
        
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
            "WebsiteURL",
            value=bucket.bucket_website_url,
            description="Website URL for static hosting",
            export_name="ProjectAppWebsiteURL",
        )

        CfnOutput(
            self,
            "BucketDomainName",
            value=bucket.bucket_domain_name,
            description="Bucket domain name",
            export_name="ProjectAppBucketDomainName",
        )