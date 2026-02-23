import json
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
search_table = dynamodb.Table(os.environ["SEARCH_TABLE_NAME"])

INDEX_NAME = "flight_status-departure_time-index"


def lambda_handler(event: dict, context) -> dict:
    query_params: dict = event.get("queryStringParameters") or {}

    status = query_params.get("status")
    if not status:
        return _response(400, {"message": "Query parameter 'status' is required."})

    from_time = query_params.get("from")
    to_time = query_params.get("to")

    key_condition = Key("flight_status").eq(status)
    if from_time and to_time:
        key_condition = key_condition & Key("departure_time").between(
            from_time, to_time
        )
    elif from_time:
        key_condition = key_condition & Key("departure_time").gte(from_time)
    elif to_time:
        key_condition = key_condition & Key("departure_time").lte(to_time)

    result = search_table.query(
        IndexName=INDEX_NAME,
        KeyConditionExpression=key_condition,
    )

    trips: list[dict[str, Any]] = result.get("Items", [])

    return _response(200, {"trips": trips, "count": len(trips)})


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
