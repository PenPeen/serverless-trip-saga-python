import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from services.flight.domain.entity.booking import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.repository import BookingRepository
from services.flight.domain.value_object import BookingId, FlightNumber
from services.shared.domain import Currency, IsoDateTime, Money, TripId
from services.shared.domain.exception.exceptions import DuplicateResourceException


class DynamoDBBookingRepository(BookingRepository):
    """DynamoDBを使用したBookingRepository の具象実装"""

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("TABLE_NAME")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def save(self, booking: Booking) -> None:
        """予約をDBに保存する"""

        item = {
            "PK": f"TRIP#{booking.trip_id}",
            "SK": f"FLIGHT#{booking.id}",
            "entity_type": "FLIGHT",
            "booking_id": str(booking.id),
            "trip_id": str(booking.trip_id),
            "flight_number": str(booking.flight_number),
            "departure_time": str(booking.departure_time),
            "arrival_time": str(booking.arrival_time),
            "price_amount": str(booking.price.amount),
            "price_currency": str(booking.price.currency),
            "status": booking.status.value,
            "GSI1PK": "TRIPS",
            "GSI1SK": f"TRIP#{booking.trip_id}",
        }
        try:
            self.table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(PK)"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateResourceException(
                    f"Booking already exists: {booking.id}"
                )

    def find_by_id(self, booking_id: BookingId) -> Booking | None:
        """予約IDで検索"""
        trip_id = str(booking_id).removeprefix("flight_for_#")
        response = self.table.get_item(
            Key={
                "PK": f"TRIP#{trip_id}",
                "SK": f"FLIGHT#{booking_id}",
            }
        )
        item = response.get("Item")
        if not item:
            return None
        return self._to_entity(item)

    def find_by_trip_id(self, trip_id: TripId) -> Booking | None:
        """Trip ID でフライト予約を検索する"""
        response = self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"TRIP#{trip_id}",
                ":sk_prefix": "FLIGHT#",
            },
        )

        items = response.get("Items", [])
        if not items:
            return None

        item = items[0]
        return self._to_entity(item)

    def _to_entity(self, item: dict) -> Booking:
        """DynamoDB アイテムをドメインエンティティに変換する"""
        return Booking(
            id=BookingId(value=item["booking_id"]),
            trip_id=TripId(value=item["trip_id"]),
            flight_number=FlightNumber(value=item["flight_number"]),
            departure_time=IsoDateTime.from_string(item["departure_time"]),
            arrival_time=IsoDateTime.from_string(item["arrival_time"]),
            price=Money(
                amount=Decimal(item["price_amount"]),
                currency=Currency(item["price_currency"]),
            ),
            status=BookingStatus(item["status"]),
        )
