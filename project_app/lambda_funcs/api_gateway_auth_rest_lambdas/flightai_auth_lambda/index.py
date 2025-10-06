import os
import json
import boto3
from http import cookies

app_client_id = os.environ["APP_CLIENT_ID"]
region = os.environ["REGION"]
cognito_client = boto3.client("cognito-idp", region_name=region)

# Prod-ready allowed origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://d2bj0it0stfal5.cloudfront.net",
]

def get_origin(event):
    """Event'ten gelen origin'i kontrol et ve allowed listede varsa kullan"""
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
        username = body["username"]
        password = body["password"]

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

        return make_response(
            200,
            {"message": "Login successful"},
            [access_cookie, refresh_cookie],
            event=event
        )

    except cognito_client.exceptions.NotAuthorizedException:
        return make_response(401, {"error": "Invalid username or password"}, event=event)
    except cognito_client.exceptions.UserNotConfirmedException:
        return make_response(403, {"error": "User not confirmed. Please verify your email."}, event=event)
    except Exception as e:
        return make_response(400, {"error": str(e)}, event=event)

def logout(event, context):
    access_cookie = "access_token=; HttpOnly; Secure; SameSite=None; Path=/; Max-Age=0"
    refresh_cookie = "refresh_token=; HttpOnly; Secure; SameSite=None; Path=/auth/refresh; Max-Age=0"
    return make_response(200, {"message": "Logged out"}, [access_cookie, refresh_cookie], event=event)

def me(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")
        c = cookies.SimpleCookie()
        c.load(cookie_header)

        access_token = c.get("access_token")
        if not access_token:
            return make_response(401, {"error": "Not authenticated"}, event=event)

        user_info = cognito_client.get_user(AccessToken=access_token.value)
        return make_response(200, {"user": user_info}, event=event)

    except Exception as e:
        return make_response(401, {"error": str(e)}, event=event)

def refresh(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")
        c = cookies.SimpleCookie()
        c.load(cookie_header)

        refresh_token = c.get("refresh_token")
        if not refresh_token:
            return make_response(401, {"error": "No refresh token found"}, event=event)

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

        return make_response(200, {"message": "Token refreshed"}, access_cookie, event=event)

    except Exception as e:
        return make_response(401, {"error": str(e)}, event=event)

def lambda_handler(event, context):
    # CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {}, event=event)

    path = event.get("path", "")
    if path.endswith("/login"):
        return login(event, context)
    elif path.endswith("/logout"):
        return logout(event, context)
    elif path.endswith("/me"):
        return me(event, context)
    elif path.endswith("/refresh"):
        return refresh(event, context)
    else:
        return make_response(404, {"error": "Not found"}, event=event)
