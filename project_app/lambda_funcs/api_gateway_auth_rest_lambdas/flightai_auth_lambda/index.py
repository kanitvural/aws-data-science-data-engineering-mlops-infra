import os
import json
import logging
import boto3
from http import cookies

# Logger setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

app_client_id = os.environ["APP_CLIENT_ID"]
region = os.environ["REGION"]
cloudfront_url = os.environ["CLOUDFRONT_URL"]
cognito_client = boto3.client("cognito-idp", region_name=region)

# Prod-ready allowed origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    cloudfront_url,
]

def get_origin(event):
    default_origin = ALLOWED_ORIGINS[0]
    if event and "headers" in event:
        request_origin = event["headers"].get("origin") or event["headers"].get("Origin")
        if request_origin and request_origin in ALLOWED_ORIGINS:
            return request_origin
    return default_origin

def make_response(status, body, cookie_headers=None, event=None):
    origin = get_origin(event)
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type, Cookie, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
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
            return make_response(400, {
                "error": "Missing credentials",
                "message": "Username and password are required"
            }, event=event)
        
        logger.info(f"Login attempt for username: {username}")

        response = cognito_client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
            ClientId=app_client_id,
        )

        tokens = response["AuthenticationResult"]

        # Prod cookie ayarları
        access_cookie = (
            f"access_token={tokens['AccessToken']}; "
            f"HttpOnly; Secure; SameSite=None; Path=/; Max-Age=3600"
        )

        refresh_cookie = (
            f"refresh_token={tokens['RefreshToken']}; "
            f"HttpOnly; Secure; SameSite=None; Path=/auth/refresh; Max-Age=2592000"
        )
        
        logger.info(f"Login successful for: {username}")
        return make_response(
            200,
            {"message": "Login successful"},
            [access_cookie, refresh_cookie],
            event=event
        )

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning(f"Invalid credentials for username: {body.get('username')}")
        return make_response(401, {
            "error": "Invalid credentials",
            "message": "Invalid username or password"
        }, event=event)
        
    except cognito_client.exceptions.UserNotConfirmedException:
        logger.warning(f"Unconfirmed user attempted login: {body.get('username')}")
        return make_response(403, {
            "error": "User not confirmed",
            "message": "Please verify your email before logging in"
        }, event=event)
        
    except cognito_client.exceptions.UserNotFoundException:
        logger.warning(f"Login attempt for non-existent user: {body.get('username')}")
        return make_response(401, {
            "error": "Invalid credentials",
            "message": "Invalid username or password"
        }, event=event)
        
    except Exception as e:
        logger.error(f"Login failed: {type(e).__name__} - {str(e)}")
        return make_response(400, {
            "error": "Login failed",
            "message": str(e)
        }, event=event)

def logout(event, context):
    logger.info("Logout request received")
    access_cookie = "access_token=; HttpOnly; Secure; SameSite=None; Path=/; Max-Age=0"
    refresh_cookie = "refresh_token=; HttpOnly; Secure; SameSite=None; Path=/auth/refresh; Max-Age=0"
    return make_response(200, {"message": "Logged out successfully"}, [access_cookie, refresh_cookie], event=event)

def me(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")
        
        if not cookie_header:
            logger.warning("Me endpoint called without cookies")
            return make_response(401, {
                "error": "Not authenticated",
                "message": "No authentication token found"
            }, event=event)
        
        c = cookies.SimpleCookie()
        c.load(cookie_header)

        access_token = c.get("access_token")
        if not access_token:
            logger.warning("Me endpoint called without access token")
            return make_response(401, {
                "error": "Not authenticated",
                "message": "No access token found"
            }, event=event)

        logger.info("Fetching user info")
        user_info = cognito_client.get_user(AccessToken=access_token.value)
        
        logger.info("User info fetched successfully")
        return make_response(200, {"user": user_info}, event=event)

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning("Invalid or expired access token")
        return make_response(401, {
            "error": "Token invalid",
            "message": "Your session has expired. Please login again"
        }, event=event)
        
    except Exception as e:
        logger.error(f"Me endpoint failed: {type(e).__name__} - {str(e)}")
        return make_response(401, {
            "error": "Authentication failed",
            "message": str(e)
        }, event=event)

def refresh(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")
        
        if not cookie_header:
            logger.warning("Refresh endpoint called without cookies")
            return make_response(401, {
                "error": "No refresh token",
                "message": "No refresh token found"
            }, event=event)
        
        c = cookies.SimpleCookie()
        c.load(cookie_header)

        refresh_token = c.get("refresh_token")
        if not refresh_token:
            logger.warning("Refresh endpoint called without refresh token")
            return make_response(401, {
                "error": "No refresh token",
                "message": "No refresh token found"
            }, event=event)

        logger.info("Refreshing access token")
        response = cognito_client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token.value},
            ClientId=app_client_id,
        )

        tokens = response["AuthenticationResult"]

        access_cookie = (
            f"access_token={tokens['AccessToken']}; "
            f"HttpOnly; Secure; SameSite=None; Path=/; Max-Age=3600"
        )
        
        logger.info("Token refreshed successfully")
        return make_response(200, {"message": "Token refreshed successfully"}, access_cookie, event=event)

    except cognito_client.exceptions.NotAuthorizedException:
        logger.warning("Invalid or expired refresh token")
        return make_response(401, {
            "error": "Refresh token invalid",
            "message": "Your refresh token has expired. Please login again"
        }, event=event)
        
    except Exception as e:
        logger.error(f"Token refresh failed: {type(e).__name__} - {str(e)}")
        return make_response(401, {
            "error": "Token refresh failed",
            "message": str(e)
        }, event=event)

def lambda_handler(event, context):
    # Log incoming request
    logger.info(f"Request: {event.get('httpMethod')} {event.get('path')}")
    
    # CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {}, event=event)

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
        return make_response(404, {
            "error": "Not found",
            "message": "Endpoint not found"
        }, event=event)
    
# 
# Frontend: d2bj0it0stfal5.cloudfront.net
# Backend: 10uz7jocr8.execute-api...

# # (more professional):
# Purchase a domain
# Frontend: myapp.com
# Backend: myapp.com/api/*  ← Same domain!

# # Fatures:
# └─> SameSite=Strict You can useStrict mode (more secure)
# └─> Easy Cookie management 
# └─> One SSL certificate
