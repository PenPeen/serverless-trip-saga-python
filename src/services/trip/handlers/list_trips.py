import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEventV2,
    event_source,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key

from services.shared.utils import api_response

logger = Logger()

TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

NUM_SHARDS = 4


@logger.inject_lambda_context
@event_source(data_class=APIGatewayProxyEventV2)
def lambda_handler(event: APIGatewayProxyEventV2, context: LambdaContext) -> dict:
    """予約一覧取得 Lambda Handler"""

    logger.info("Listing all trips")

    try:
        all_items: list[dict] = []
        for shard in range(NUM_SHARDS):
            response = table.query(
                IndexName="GSI1",
                KeyConditionExpression=Key("GSI1PK").eq(f"TRIPS#{shard}"),
            )
            all_items.extend(response.get("Items", []))

        trips = [{"trip_id": item["trip_id"]} for item in all_items]
        return api_response(200, {"trips": trips, "count": len(trips)})

    except Exception:
        logger.exception("Failed to list trips")
        return api_response(500, {"message": "Internal server error"})
