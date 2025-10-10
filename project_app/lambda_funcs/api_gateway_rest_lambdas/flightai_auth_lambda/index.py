# ==================== AUTH LAMBDA ====================

import os
import json
import logging
import boto3
from http import cookies

# === LAMBDA LOGGER SETUP ===
logger = logging.getLogger()
logger.setLevel(logging.INFO)

if not logger.handlers:
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

app_client_id = os.environ["APP_CLIENT_ID"]
region = os.environ["REGION"]
CLOUDFRONT_URL = os.environ["CLOUDFRONT_URL"]
cognito_client = boto3.client("cognito-idp", region_name=region)


# Get origin from event
def get_origin(event):
    return event.get("headers", {}).get("origin", CLOUDFRONT_URL)


def make_response(status, body, event, cookie_headers=None):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": get_origin(event), 
        "Access-Control-Allow-Credentials": "true",
    }

    multi_value_headers = {}
    if cookie_headers:
        if isinstance(cookie_headers, list):
            multi_value_headers["Set-Cookie"] = cookie_headers
        else:
            multi_value_headers["Set-Cookie"] = [cookie_headers]

    return {
        "statusCode": status,
        "headers": headers,
        "multiValueHeaders": multi_value_headers,
        "body": json.dumps(body),
    }


def login(event, context):
    try:
        body = json.loads(event["body"])
        username = body.get("username")
        password = body.get("password")

        if not username or not password:
            logger.warning("Login attempt with missing credentials")
            return make_response(
                400, 
                {"error": "Missing credentials", "message": "Username and password are required"},
                event  
            )

        logger.info(f"Login attempt for username: {username}")

        response = cognito_client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
            ClientId=app_client_id,
        )

        tokens = response["AuthenticationResult"]

        # Prod cookie configurations
        access_cookie = (
            f"access_token={tokens['AccessToken']}; "
            "HttpOnly; Secure; SameSite=None; Path=/; Max-Age=3600"
        )

        refresh_cookie = (
            f"refresh_token={tokens['RefreshToken']}; "
            "HttpOnly; Secure; SameSite=None; Path=/auth/refresh; Max-Age=2592000"
        )

        logger.info(f"Login successful for: {username}")
        return make_response(
            200,
            {"message": "Login successful"},
            event,  
            [access_cookie, refresh_cookie],
        )

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning(f"Invalid credentials for username: {body.get('username')}")
        return make_response(
            401, 
            {"error": "Invalid credentials", "message": "Invalid username or password"},
            event  
        )

    except cognito_client.exceptions.UserNotConfirmedException:
        logger.warning(f"Unconfirmed user attempted login: {body.get('username')}")
        return make_response(
            403, 
            {"error": "User not confirmed", "message": "Please verify your email before logging in"},
            event  
        )

    except cognito_client.exceptions.UserNotFoundException:
        logger.warning(f"Login attempt for non-existent user: {body.get('username')}")
        return make_response(
            401, 
            {"error": "Invalid credentials", "message": "Invalid username or password"},
            event  
        )

    except Exception as e:
        logger.error(f"Login failed: {type(e).__name__} - {str(e)}")
        return make_response(
            400, 
            {"error": "Login failed", "message": str(e)},
            event  
        )


def logout(event, context):
    logger.info("Logout request received")
    access_cookie = "access_token=; HttpOnly; Secure; SameSite=None; Path=/; Max-Age=0"
    refresh_cookie = "refresh_token=; HttpOnly; Secure; SameSite=None; Path=/auth/refresh; Max-Age=0"
    return make_response(
        200,
        {"message": "Logged out successfully"},
        event,  
        [access_cookie, refresh_cookie],
    )


def me(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")

        if not cookie_header:
            logger.warning("Me endpoint called without cookies")
            return make_response(
                401, 
                {"error": "Not authenticated", "message": "No authentication token found"},
                event  
            )

        cookie = cookies.SimpleCookie()
        cookie.load(cookie_header)

        access_token = cookie.get("access_token")
        if not access_token:
            logger.warning("Me endpoint called without access token")
            return make_response(
                401, 
                {"error": "Not authenticated", "message": "No access token found"},
                event  
            )

        logger.info("Fetching user info")
        user_info = cognito_client.get_user(AccessToken=access_token.value)

        logger.info("User info fetched successfully")
        return make_response(
            200, 
            {"user": user_info},
            event  
        )

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning("Invalid or expired access token")
        return make_response(
            401, 
            {"error": "Token invalid", "message": "Your session has expired. Please login again"},
            event  
        )

    except Exception as e:
        logger.error(f"Me endpoint failed: {type(e).__name__} - {str(e)}")
        return make_response(
            401, 
            {"error": "Authentication failed", "message": str(e)},
            event  
        )


def refresh(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")

        if not cookie_header:
            logger.warning("Refresh endpoint called without cookies")
            return make_response(
                401, 
                {"error": "No refresh token", "message": "No refresh token found"},
                event  
            )

        cookie = cookies.SimpleCookie()
        cookie.load(cookie_header)

        refresh_token = cookie.get("refresh_token")
        if not refresh_token:
            logger.warning("Refresh endpoint called without refresh token")
            return make_response(
                401, 
                {"error": "No refresh token", "message": "No refresh token found"},
                event  
            )

        logger.info("Refreshing access token")
        response = cognito_client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token.value},
            ClientId=app_client_id,
        )

        tokens = response["AuthenticationResult"]

        access_cookie = (
            f"access_token={tokens['AccessToken']}; "
            "HttpOnly; Secure; SameSite=None; Path=/; Max-Age=3600"
        )

        logger.info("Token refreshed successfully")
        return make_response(
            200, 
            {"message": "Token refreshed successfully"},
            event,  
            access_cookie
        )

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning("Invalid or expired refresh token")
        return make_response(
            401, 
            {"error": "Refresh token invalid", "message": "Your refresh token has expired. Please login again"},
            event  
        )

    except Exception as e:
        logger.error(f"Token refresh failed: {type(e).__name__} - {str(e)}")
        return make_response(
            401, 
            {"error": "Token refresh failed", "message": str(e)},
            event  
        )


def lambda_handler(event, context):
    # Log incoming request
    logger.info(f"Request: {event.get('httpMethod')} {event.get('path')}")

    path = event.get("path", "")

    # Route to appropriate handler
    if path.endswith("/login"):
        return login(event, context)
    elif path.endswith("/logout"):
        return logout(event, context)
    elif path.endswith("/me"):
        return me(event, context)
    elif path.endswith("/refresh"):
        return refresh(event, context)
    else:
        logger.warning(f"Unknown endpoint: {path}")
        return make_response(
            404, 
            {"error": "Not found", "message": "Endpoint not found"},
            event  
        )