import os
from decimal import Decimal
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from services.hotel.domain.entity import HotelBooking
from services.hotel.domain.enum import HotelBookingStatus
from services.hotel.domain.repository import HotelBookingRepository
from services.hotel.domain.value_object import HotelBookingId, HotelName, StayPeriod
from services.shared.domain import Currency, Money, TripId
from services.shared.domain.exception.exceptions import DuplicateResourceException


class DynamoDBHotelBookingRepository(HotelBookingRepository):
    """DynamoDBを使用したHotelBookingRepository の具象実装"""

    def __init__(self, table_name: Optional[str] = None) -> None:
        self.table_name = table_name or os.getenv("TABLE_NAME")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def save(self, booking: HotelBooking) -> None:
        """予約をDBに保存する"""
        item = {
            "PK": f"TRIP#{booking.trip_id}",
            "SK": f"HOTEL#{booking.id}",
            "entity_type": "HOTEL",
            "booking_id": str(booking.id),
            "trip_id": str(booking.trip_id),
            "hotel_name": str(booking.hotel_name),
            "check_in_date": booking.stay_period.check_in,
            "check_out_date": booking.stay_period.check_out,
            "price_amount": str(booking.price.amount),
            "price_currency": str(booking.price.currency),
            "status": booking.status.value,
        }
        try:
            self.table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(PK)"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateResourceException(
                    f"Hotel booking already exists: {booking.id}"
                )

    def find_by_id(self, booking_id: HotelBookingId) -> Optional[HotelBooking]:
        """予約IDで検索"""
        response = self.table.scan(
            FilterExpression="booking_id = :bid",
            ExpressionAttributeValues={":bid": str(booking_id)},
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_entity(items[0])

    def find_by_trip_id(self, trip_id: TripId) -> Optional[HotelBooking]:
        """Trip ID でホテル予約を検索する"""
        response = self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"TRIP#{trip_id}",
                ":sk_prefix": "HOTEL#",
            },
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_entity(items[0])

    def _to_entity(self, item: dict) -> HotelBooking:
        """DynamoDB アイテムをドメインエンティティに変換する"""
        return HotelBooking(
            id=HotelBookingId(value=item["booking_id"]),
            trip_id=TripId(value=item["trip_id"]),
            hotel_name=HotelName(value=item["hotel_name"]),
            stay_period=StayPeriod(
                check_in=item["check_in_date"],
                check_out=item["check_out_date"],
            ),
            price=Money(
                amount=Decimal(item["price_amount"]),
                currency=Currency(item["price_currency"]),
            ),
            status=HotelBookingStatus(item["status"]),
        )
