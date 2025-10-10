import os
import json
import logging
import boto3
from http import cookies as http_cookies

logger = logging.getLogger()
logger.setLevel(logging.INFO)

region = os.environ["REGION"]
user_pool_id = os.environ["USER_POOL_ID"]

cognito_client = boto3.client("cognito-idp", region_name=region)


def generate_policy(principal_id, effect, resource, context=None):
    """Generate IAM policy for API Gateway"""
    auth_response = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}],
        },
    }

    # Add context (will be available in Lambda as event['requestContext']['authorizer'])
    if context:
        auth_response["context"] = context

    return auth_response


def lambda_handler(event, context):
    """
    Lambda Authorizer for API Gateway
    Extracts access_token from HttpOnly cookie and validates with Cognito
    """
    try:
        logger.info("Authorizer invoked")
        logger.info(f"Event: {json.dumps(event)}")

        # Get Cookie header
        headers = event.get("headers", {})
        cookie_header = headers.get("cookie") or headers.get("Cookie") or ""

        if not cookie_header:
            logger.warning("No cookie header found")
            raise Exception("Unauthorized: No cookie found")

        # Parse cookies
        cookie = http_cookies.SimpleCookie()
        cookie.load(cookie_header)

        # Extract access_token
        access_token_cookie = cookie.get("access_token")
        if not access_token_cookie:
            logger.warning("No access_token in cookies")
            raise Exception("Unauthorized: No access token found")

        access_token = access_token_cookie.value
        logger.info("Access token found in cookie")

        # Validate token with Cognito
        try:
            user_response = cognito_client.get_user(AccessToken=access_token)
            logger.info(f"Token validated successfully")

            # Extract user attributes
            user_attributes = user_response.get("UserAttributes", [])
            username = user_response.get("Username")  # This is the 'sub' (user ID)

            # Find specific attributes
            user_id = username  # Cognito's Username is the 'sub'
            email = None
            given_name = None

            for attr in user_attributes:
                if attr["Name"] == "sub":
                    user_id = attr["Value"]
                elif attr["Name"] == "email":
                    email = attr["Value"]
                elif attr["Name"] == "given_name":
                    given_name = attr["Value"]

            logger.info(f"User authenticated: {user_id}")

            # Generate Allow policy with user context
            # This context will be available in Lambda functions
            auth_context = {"userId": user_id, "email": email or "", "givenName": given_name or ""}

            # Get method ARN for policy
            method_arn = event["methodArn"]

            # Allow access to all methods in this API
            # Replace specific method with wildcard
            arn_parts = method_arn.split(":")
            api_gateway_arn = arn_parts[5].split("/")
            resource = f"{':'.join(arn_parts[:5])}:{api_gateway_arn[0]}/{api_gateway_arn[1]}/*/*"

            return generate_policy(user_id, "Allow", resource, auth_context)

        except cognito_client.exceptions.NotAuthorizedException:
            logger.warning("Invalid or expired token")
            raise Exception("Unauthorized: Invalid token")
        except cognito_client.exceptions.UserNotFoundException:
            logger.warning("User not found")
            raise Exception("Unauthorized: User not found")
        except Exception as e:
            logger.error(f"Cognito validation error: {str(e)}")
            raise Exception(f"Unauthorized: {str(e)}")

    except Exception as e:
        logger.error(f"Authorization failed: {str(e)}")
        # Return Deny policy
        raise Exception("Unauthorized")
