import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEventV2,
    event_source,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.shared.utils import api_response

logger = Logger()

TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


@logger.inject_lambda_context
@event_source(data_class=APIGatewayProxyEventV2)
def lambda_handler(event: APIGatewayProxyEventV2, context: LambdaContext) -> dict:
    """予約一覧取得 Lambda Handler"""

    logger.info("Listing all trips")

    try:
        response = table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": "TRIPS"},
        )

        items = response.get("Items", [])
        trips = _deduplicate_trips(items)
        return api_response(200, {"trips": trips, "count": len(trips)})

    except Exception:
        logger.exception("Failed to list trips")
        return api_response(500, {"message": "Internal server error"})


def _deduplicate_trips(items: list[dict]) -> list[dict]:
    """GSI から取得したアイテムを trip_id で重複排除する

    1つの trip_id に対して FLIGHT・HOTEL・PAYMENT の3アイテムが GSI に存在するため、
        trip_id の一意なリストに変換する
    """

    seen: set[str] = set()
    trips: list[dict] = []

    for item in items:
        trip_id = item.get("trip_id", "")
        if trip_id and trip_id not in seen:
            seen.add(trip_id)
            trips.append({"trip_id": trip_id})

    return trips
