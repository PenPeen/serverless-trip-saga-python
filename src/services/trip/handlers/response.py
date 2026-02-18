import json


def build_response(status_code: int, body: dict) -> dict:
    """API Gateway Lambda Proxy Integration のレスポンス形式を生成する"""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
