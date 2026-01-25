import os
from decimal import Decimal
from typing import Optional

import boto3

from services.flight.domain.entity.booking import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.repository import BookingRepository
from services.flight.domain.value_object import BookingId, FlightNumber
from services.shared.domain import Currency, IsoDateTime, Money, TripId


class DynamoDBBookingRepository(BookingRepository):
    """DynamoDBを使用したBookingRepository の具象実装"""

    def __init__(self, table_name: Optional[str] = None) -> None:
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
        }
        self.table.put_item(Item=item)

    def find_by_id(self, booking_id: BookingId) -> Optional[Booking]:
        """予約IDで検索"""
        response = self.table.scan(
            FilterExpression="booking_id = :bid",
            ExpressionAttributeValues={":bid": str(booking_id)},
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_entity(items[0])

    def find_by_trip_id(self, trip_id: TripId) -> Optional[Booking]:
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
