import os
import json
import boto3


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

    return {
        "statusCode": status,
        "headers": headers,
        "multiValueHeaders": multi_value_headers,
        "body": json.dumps(body),
    }


def signup(event, context):
    try:
        body = json.loads(event["body"])
        username = body["username"]
        password = body["password"]
        email = body["email"]
        first_name = body["firstName"]   
        last_name = body["lastName"]   
        gender = body["gender"]

        cognito_client.sign_up(
            ClientId=app_client_id,
            Username=username,
            Password=password,
            UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "given_name", "Value": first_name},
            {"Name": "family_name", "Value": last_name},
            {"Name": "gender", "Value": gender},
            ],
        )

        return make_response(200, {"message": "Signup successful. Please check your email for verification code."})
    except cognito_client.exceptions.UsernameExistsException:
        return make_response(400, {"error": "User already exists"})
    except cognito_client.exceptions.InvalidPasswordException as e:
        return make_response(400, {"error": str(e)})
    except Exception as e:
        return make_response(400, {"error": str(e)})


def confirm(event, context):
    try:
        body = json.loads(event["body"])
        username = body["username"]
        code = body["code"]

        cognito_client.confirm_sign_up(
            ClientId=app_client_id,
            Username=username,
            ConfirmationCode=code,
        )

        return make_response(200, {"message": "Email verified successfully"})
    except cognito_client.exceptions.CodeMismatchException:
        return make_response(400, {"error": "Invalid verification code"})
    except cognito_client.exceptions.ExpiredCodeException:
        return make_response(400, {"error": "Verification code expired"})
    except Exception as e:
        return make_response(400, {"error": str(e)})


def forgot_password(event, context):
    try:
        body = json.loads(event["body"])
        username = body["username"]

        cognito_client.forgot_password(
            ClientId=app_client_id,
            Username=username,
        )

        return make_response(200, {"message": "Password reset code sent to your email"})
    except Exception as e:
        return make_response(400, {"error": str(e)})


def confirm_forgot_password(event, context):
    try:
        body = json.loads(event["body"])
        username = body["username"]
        code = body["code"]
        new_password = body["new_password"]

        cognito_client.confirm_forgot_password(
            ClientId=app_client_id,
            Username=username,
            ConfirmationCode=code,
            Password=new_password,
        )

        return make_response(200, {"message": "Password reset successful"})
    except Exception as e:
        return make_response(400, {"error": str(e)})


def lambda_handler(event, context):
    # CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {})

    path = event.get("path", "")

    if path.endswith("/signup"):
        return signup(event, context)
    elif path.endswith("/confirm"):
        return confirm(event, context)
    elif path.endswith("/forgot-password"):
        return forgot_password(event, context)
    elif path.endswith("/confirm-forgot-password"):
        return confirm_forgot_password(event, context)
    else:
        return make_response(404, {"error": "Not found"})
