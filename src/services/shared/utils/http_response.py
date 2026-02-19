import json


def api_response(status_code: int, body: dict) -> dict:
    """API Gateway HTTP API のレスポンス形式を生成する"""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
