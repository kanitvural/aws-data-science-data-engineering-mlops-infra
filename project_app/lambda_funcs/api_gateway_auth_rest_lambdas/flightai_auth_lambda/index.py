import os
import json
import boto3
from http import cookies


app_client_id = os.environ["APP_CLIENT_ID"]
region = os.environ["REGION"]
cognito_client = boto3.client("cognito-idp", region_name= region)


def make_response(status, body, cookie_headers=None):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "http://localhost:3000",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
    }

    multi_value_headers = {}
    if cookie_headers:
        if isinstance(cookie_headers, list):
            multi_value_headers["Set-Cookie"] = cookie_headers
        else:
            multi_value_headers["Set-Cookie"] = [cookie_headers]
    else:
        multi_value_headers = {}

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

        # Production
        # access_cookie = (
        #     f"access_token={tokens['AccessToken']}; "
        #     f"HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600"
        # )

        # refresh_cookie = (
        #     f"refresh_token={tokens['RefreshToken']}; "
        #     f"HttpOnly; Secure; SameSite=Strict; Path=/auth/refresh; Max-Age=2592000"
        # )

        # Local test
        access_cookie = (
            f"access_token={tokens['AccessToken']}; "
            f"HttpOnly; Secure=False; SameSite=None; Path=/; Max-Age=3600"
        )

        refresh_cookie = (
            f"refresh_token={tokens['RefreshToken']}; "
            f"HttpOnly; Secure=False; SameSite=None; Path=/auth/refresh; Max-Age=2592000"
        )

        return make_response(
            200,
            {"message": "Login successful"},
            [access_cookie, refresh_cookie],
        )

    except cognito_client.exceptions.NotAuthorizedException:
        return make_response(401, {"error": "Invalid username or password"})
    except cognito_client.exceptions.UserNotConfirmedException:
        return make_response(403, {"error": "User not confirmed. Please verify your email."})
    except Exception as e:
        return make_response(400, {"error": str(e)})


def logout(event, context):
    access_cookie = (
        "access_token=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0"
    )
    refresh_cookie = (
        "refresh_token=; HttpOnly; Secure; SameSite=Strict; Path=/auth/refresh; Max-Age=0"
    )
    return make_response(200, {"message": "Logged out"}, [access_cookie, refresh_cookie])


def me(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")
        c = cookies.SimpleCookie()
        c.load(cookie_header)

        access_token = c.get("access_token")
        if not access_token:
            return make_response(401, {"error": "Not authenticated"})

        user_info = cognito_client.get_user(AccessToken=access_token.value)

        return make_response(200, {"user": user_info})
    except Exception as e:
        return make_response(401, {"error": str(e)})


def refresh(event, context):
    try:
        cookie_header = event["headers"].get("cookie", "")
        c = cookies.SimpleCookie()
        c.load(cookie_header)

        refresh_token = c.get("refresh_token")
        if not refresh_token:
            return make_response(401, {"error": "No refresh token found"})

        response = cognito_client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token.value},
            ClientId=app_client_id,
        )

        tokens = response["AuthenticationResult"]

        access_cookie = (
            f"access_token={tokens['AccessToken']}; "
            f"HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600"
        )

        return make_response(200, {"message": "Token refreshed"}, access_cookie)

    except Exception as e:
        return make_response(401, {"error": str(e)})


def lambda_handler(event, context):
    # CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {})
    
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
        return make_response(404, {"error": "Not found"})