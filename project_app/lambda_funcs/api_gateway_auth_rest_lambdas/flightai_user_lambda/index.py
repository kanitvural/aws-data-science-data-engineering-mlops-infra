import os
import json
import logging
import boto3

# Logger setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

app_client_id = os.environ["APP_CLIENT_ID"]
region = os.environ["REGION"]
cloudfront_url = os.environ["CLOUDFRONT_URL"]
cognito_client = boto3.client("cognito-idp", region_name=region)


def make_response(status, body, cookie_headers=None, event=None):
    # Allowed origins
    allowed_origins = [
        "http://localhost:3000",
        cloudfront_url,
    ]

    # Default origin
    origin = allowed_origins[0]

    # Check origin that coming from Request
    if event and "headers" in event:
        headers = event["headers"]
        request_origin = headers.get("origin") or headers.get("Origin")
        if request_origin and request_origin in allowed_origins:
            origin = request_origin

    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type, Cookie, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
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

        # Validate required fields
        required_fields = ["username", "password", "email", "firstName", "lastName", "gender"]
        missing_fields = [field for field in required_fields if not body.get(field)]

        if missing_fields:
            logger.warning(f"Signup attempt with missing fields: {missing_fields}")
            return make_response(
                400,
                {"error": "Missing required fields", "message": f"Please provide: {', '.join(missing_fields)}"},
                event=event,
            )

        username = body["username"]
        password = body["password"]
        email = body["email"]
        first_name = body["firstName"]
        last_name = body["lastName"]
        gender = body["gender"]

        # Basic email validation
        if "@" not in email or "." not in email:
            logger.warning(f"Invalid email format: {email}")
            return make_response(
                400, {"error": "Invalid email", "message": "Please provide a valid email address"}, event=event
            )

        logger.info(f"Signup attempt for username: {username}, email: {email}")

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

        logger.info(f"Signup successful for: {username}")
        return make_response(
            200, {"message": "Signup successful. Please check your email for verification code."}, event=event
        )

    except cognito_client.exceptions.UsernameExistsException:
        logger.warning(f"Username already exists: {body.get('username')}")
        return make_response(
            400,
            {"error": "User already exists", "message": "This username is already taken. Please choose another one."},
            event=event,
        )

    except cognito_client.exceptions.InvalidPasswordException as e:
        logger.warning(f"Invalid password for user: {body.get('username')}")
        return make_response(400, {"error": "Invalid password", "message": str(e)}, event=event)

    except Exception as e:
        logger.error(f"Signup failed: {type(e).__name__} - {str(e)}")
        return make_response(400, {"error": "Signup failed", "message": str(e)}, event=event)


def confirm(event, context):
    try:
        body = json.loads(event["body"])

        username = body.get("username")
        code = body.get("code")

        if not username or not code:
            logger.warning("Confirm attempt with missing fields")
            return make_response(
                400,
                {"error": "Missing required fields", "message": "Username and verification code are required"},
                event=event,
            )

        logger.info(f"Email confirmation attempt for: {username}")

        cognito_client.confirm_sign_up(
            ClientId=app_client_id,
            Username=username,
            ConfirmationCode=code,
        )

        logger.info(f"Email confirmed successfully for: {username}")
        return make_response(200, {"message": "Email verified successfully. You can now login."}, event=event)

    except cognito_client.exceptions.CodeMismatchException:
        logger.warning(f"Invalid verification code for: {body.get('username')}")
        return make_response(
            400,
            {"error": "Invalid code", "message": "The verification code you entered is incorrect. Please try again."},
            event=event,
        )

    except cognito_client.exceptions.ExpiredCodeException:
        logger.warning(f"Expired verification code for: {body.get('username')}")
        return make_response(
            400,
            {"error": "Code expired", "message": "Your verification code has expired. Please request a new one."},
            event=event,
        )

    except cognito_client.exceptions.UserNotFoundException:
        logger.warning(f"User not found during confirmation: {body.get('username')}")
        return make_response(
            404, {"error": "User not found", "message": "No user found with this username."}, event=event
        )

    except Exception as e:
        logger.error(f"Confirmation failed: {type(e).__name__} - {str(e)}")
        return make_response(400, {"error": "Confirmation failed", "message": str(e)}, event=event)


def forgot_password(event, context):
    try:
        body = json.loads(event["body"])
        username = body.get("username")

        if not username:
            logger.warning("Forgot password attempt without username")
            return make_response(400, {"error": "Missing username", "message": "Username is required"}, event=event)

        logger.info(f"Password reset requested for: {username}")

        cognito_client.forgot_password(
            ClientId=app_client_id,
            Username=username,
        )

        logger.info(f"Password reset code sent for: {username}")
        return make_response(
            200, {"message": "If this user exists, a password reset code has been sent to their email"}, event=event
        )

    except cognito_client.exceptions.UserNotFoundException:
        # Security: Don't reveal if user exists
        logger.warning(f"Password reset attempted for non-existent user: {body.get('username')}")
        return make_response(
            200, {"message": "If this user exists, a password reset code has been sent to their email"}, event=event
        )

    except Exception as e:
        logger.error(f"Forgot password failed: {type(e).__name__} - {str(e)}")
        return make_response(400, {"error": "Password reset request failed", "message": str(e)}, event=event)


def confirm_forgot_password(event, context):
    try:
        body = json.loads(event["body"])

        username = body.get("username")
        code = body.get("code")
        new_password = body.get("new_password")

        if not username or not code or not new_password:
            logger.warning("Password reset confirmation with missing fields")
            return make_response(
                400,
                {"error": "Missing required fields", "message": "Username, code, and new password are required"},
                event=event,
            )

        logger.info(f"Password reset confirmation for: {username}")

        cognito_client.confirm_forgot_password(
            ClientId=app_client_id,
            Username=username,
            ConfirmationCode=code,
            Password=new_password,
        )

        logger.info(f"Password reset successful for: {username}")
        return make_response(
            200, {"message": "Password reset successful. You can now login with your new password."}, event=event
        )

    except cognito_client.exceptions.CodeMismatchException:
        logger.warning(f"Invalid reset code for: {body.get('username')}")
        return make_response(
            400,
            {"error": "Invalid code", "message": "The reset code you entered is incorrect. Please try again."},
            event=event,
        )

    except cognito_client.exceptions.ExpiredCodeException:
        logger.warning(f"Expired reset code for: {body.get('username')}")
        return make_response(
            400,
            {"error": "Code expired", "message": "Your reset code has expired. Please request a new one."},
            event=event,
        )

    except cognito_client.exceptions.InvalidPasswordException as e:
        logger.warning(f"Invalid new password for: {body.get('username')}")
        return make_response(400, {"error": "Invalid password", "message": str(e)}, event=event)

    except cognito_client.exceptions.UserNotFoundException:
        logger.warning(f"User not found during password reset: {body.get('username')}")
        return make_response(
            404, {"error": "User not found", "message": "No user found with this username."}, event=event
        )

    except Exception as e:
        logger.error(f"Password reset confirmation failed: {type(e).__name__} - {str(e)}")
        return make_response(400, {"error": "Password reset failed", "message": str(e)}, event=event)


def lambda_handler(event, context):
    # Log incoming request
    logger.info(f"Request: {event.get('httpMethod')} {event.get('path')}")

    # CORS Preflight
    if event.get("httpMethod") == "OPTIONS":
        return make_response(200, {}, event=event)

    path = event.get("path", "")

    # Route to appropriate handler
    if path.endswith("/signup"):
        return signup(event, context)
    elif path.endswith("/confirm"):
        return confirm(event, context)
    elif path.endswith("/forgot-password"):
        return forgot_password(event, context)
    elif path.endswith("/confirm-forgot-password"):
        return confirm_forgot_password(event, context)
    else:
        logger.warning(f"Unknown endpoint: {path}")
        return make_response(404, {"error": "Not found", "message": "Endpoint not found"}, event=event)


###########################
# Improvements if need
###########################

#  Resend Confirmation Code

# def resend_confirmation(event, context):
#     try:
#         body = json.loads(event["body"])
#         username = body["username"]

#         cognito_client.resend_confirmation_code(
#             ClientId=app_client_id,
#             Username=username
#         )

#         return make_response(200, {
#             "message": "Verification code resent to your email"
#         }, event=event)

#     except Exception as e:
#         logger.error(f"Resend confirmation failed: {str(e)}")
#         return make_response(400, {"error": str(e)}, event=event)


# Input Validation

# def signup(event, context):
#     try:
#         body = json.loads(event["body"])

#         # ✅ Required fields kontrolü
#         required_fields = ["username", "password", "email", "firstName", "lastName", "gender"]
#         for field in required_fields:
#             if field not in body or not body[field]:
#                 return make_response(400, {"error": f"Missing required field: {field}"}, event=event)

#         username = body["username"]
#         password = body["password"]
#         email = body["email"]
#         first_name = body["firstName"]
#         last_name = body["lastName"]
#         gender = body["gender"]

#         # ✅ Email format kontrolü (basit)
#         if "@" not in email:
#             return make_response(400, {"error": "Invalid email format"}, event=event)

#         # ... rest of code
