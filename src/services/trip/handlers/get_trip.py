import os
from typing import Callable

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


@logger.inject_lambda_context
@event_source(data_class=APIGatewayProxyEventV2)
def lambda_handler(event: APIGatewayProxyEventV2, context: LambdaContext) -> dict:
    """予約詳細取得 Lambda Handler"""

    path_params = event.path_parameters or {}
    trip_id = path_params.get("trip_id")

    if not trip_id:
        return api_response(400, {"message": "trip_id is required"})

    logger.info("Fetching trip details", extra={"trip_id": trip_id})

    try:
        response = table.query(
            KeyConditionExpression=Key("PK").eq(f"TRIP#{trip_id}"),
        )

        items = response.get("Items", [])
        if not items:
            return api_response(404, {"message": f"Trip not found: {trip_id}"})

        trip = _assemble_trip(trip_id, items)
        return api_response(200, trip)

    except Exception:
        logger.exception("Failed to fetch trip details")
        return api_response(500, {"message": "Internal server error"})


def _build_flight(item: dict) -> dict:
    return {
        "booking_id": item["booking_id"],
        "flight_number": item["flight_number"],
        "departure_time": item["departure_time"],
        "arrival_time": item["arrival_time"],
        "price_amount": item["price_amount"],
        "price_currency": item["price_currency"],
        "status": item["status"],
    }


def _build_hotel(item: dict) -> dict:
    return {
        "booking_id": item["booking_id"],
        "hotel_name": item["hotel_name"],
        "check_in_date": item["check_in_date"],
        "check_out_date": item["check_out_date"],
        "price_amount": item["price_amount"],
        "price_currency": item["price_currency"],
        "status": item["status"],
    }


def _build_payment(item: dict) -> dict:
    return {
        "payment_id": item["payment_id"],
        "amount": item["amount"],
        "currency": item["currency"],
        "status": item["status"],
    }


_ENTITY_ASSEMBLERS: dict[str, tuple[str, Callable[[dict], dict]]] = {
    "FLIGHT": ("flight", _build_flight),
    "HOTEL": ("hotel", _build_hotel),
    "PAYMENT": ("payment", _build_payment),
}


def _assemble_trip(trip_id: str, items: list[dict]) -> dict:
    """DynamoDB の複数アイテムを1つの旅行レスポンスに結合する"""
    trip: dict = {"trip_id": trip_id}

    for item in items:
        entity_type = item.get("entity_type")
        if entity_type in _ENTITY_ASSEMBLERS:
            trip_key, build = _ENTITY_ASSEMBLERS[entity_type]
            trip[trip_key] = build(item)

    return trip
