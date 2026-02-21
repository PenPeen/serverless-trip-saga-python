import hmac
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_secret_cache: str | None = None


def _get_secret() -> str:
    global _secret_cache
    if _secret_cache is None:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(
            SecretId=os.environ["ORIGIN_VERIFY_SECRET_ARN"]
        )
        _secret_cache = response["SecretString"]
    return _secret_cache


def lambda_handler(event, context):
    headers = event.get("headers", {})
    actual = headers.get("x-origin-verify", "")
    expected = _get_secret()

    if not hmac.compare_digest(actual, expected):
        raise Exception("Unauthorized")

    method_arn = event["methodArn"]
    arn_parts = method_arn.split(":")
    region = arn_parts[3]
    account_id = arn_parts[4]
    api_gw_arn = arn_parts[5]
    rest_api_id = api_gw_arn.split("/")[0]
    stage = api_gw_arn.split("/")[1]
    resource_arn = (
        f"arn:aws:execute-api:{region}:{account_id}:{rest_api_id}/{stage}/*/*"
    )

    return {
        "principalId": "cloudfront",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": resource_arn,
                }
            ],
        },
    }
