# project_app/scripts/cloudfront_cache_invalidation.py
import os
import boto3
import logging
import sys
from datetime import datetime

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

bucket_name = os.getenv("BUCKET_NAME", "project-app-bucket-058264126563")

cloudfront_client = boto3.client("cloudfront", region_name="eu-central-1")

def invalidate_cloudfront(bucket_name):
    """
    Find CloudFront distribution by origin domain substring and invalidate its cache.
    """
    try:
        response = cloudfront_client.list_distributions()
        for dist in response.get("DistributionList", {}).get("Items", []):
            for origin in dist.get("Origins", {}).get("Items", []):
                domain_name = origin.get("DomainName", "")
                if bucket_name in domain_name:
                    dist_id = dist["Id"]
                    logger.info(f"Found distribution ID: {dist_id}, creating invalidation...")

                    caller_reference = f"invalidation-{datetime.utcnow().isoformat()}"
                    cf_response = cloudfront_client.create_invalidation(
                        DistributionId=dist_id,
                        InvalidationBatch={
                            'Paths': {'Quantity': 1, 'Items': ['/*']},
                            'CallerReference': caller_reference
                        }
                    )
                    invalidation_id = cf_response['Invalidation']['Id']
                    logger.info(f"Invalidation submitted successfully: {invalidation_id}")
                    return cf_response

        logger.warning(f"No CloudFront distribution found with origin containing '{bucket_name}'")
        return None

    except Exception as e:
        logger.error(f"Failed to invalidate CloudFront: {e}")
        return None


if __name__ == "__main__":
    invalidate_cloudfront(bucket_name)
