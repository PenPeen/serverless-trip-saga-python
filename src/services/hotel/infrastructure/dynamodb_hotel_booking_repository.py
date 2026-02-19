import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from services.hotel.domain.entity import HotelBooking
from services.hotel.domain.enum import HotelBookingStatus
from services.hotel.domain.repository import HotelBookingRepository
from services.hotel.domain.value_object import HotelBookingId, HotelName, StayPeriod
from services.shared.domain import Currency, Money, TripId
from services.shared.domain.exception.exceptions import (
    DuplicateResourceException,
    OptimisticLockException,
)


class DynamoDBHotelBookingRepository(HotelBookingRepository):
    """DynamoDBを使用したHotelBookingRepository の具象実装"""

    def __init__(self, table_name: str | None = None) -> None:
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
            "GSI1PK": "TRIPS",
            "GSI1SK": f"TRIP#{booking.trip_id}",
        }
        try:
            self.table.put_item(Item=item, ConditionExpression=Attr("PK").not_exists())
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateResourceException(
                    f"Hotel booking already exists: {booking.id}"
                )

    def find_by_id(self, booking_id: HotelBookingId) -> HotelBooking | None:
        """予約IDで検索"""
        trip_id = str(booking_id).removeprefix("hotel_for_")
        response = self.table.get_item(
            Key={
                "PK": f"TRIP#{trip_id}",
                "SK": f"HOTEL#{booking_id}",
            },
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None
        return self._to_entity(item)

    def find_by_trip_id(self, trip_id: TripId) -> HotelBooking | None:
        """Trip ID でホテル予約を検索する"""
        response = self.table.query(
            KeyConditionExpression=Key("PK").eq(f"TRIP#{trip_id}")
            & Key("SK").begins_with("HOTEL#"),
            ConsistentRead=True,
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_entity(items[0])

    def update(
        self, booking: HotelBooking, expected_status: HotelBookingStatus | None = None
    ) -> None:
        """予約のステータスを更新する"""
        kwargs: dict = {
            "Key": {
                "PK": f"TRIP#{booking.trip_id}",
                "SK": f"HOTEL#{booking.id}",
            },
            "UpdateExpression": "SET #status = :status",
            "ExpressionAttributeNames": {"#status": "status"},
            "ExpressionAttributeValues": {":status": booking.status.value},
        }

        if expected_status is not None:
            kwargs["ConditionExpression"] = Attr("status").eq(expected_status.value)

        try:
            self.table.update_item(**kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise OptimisticLockException(
                    f"Hotel booking status conflict: "
                    f"expected {expected_status}, "
                    f"booking_id={booking.id}"
                )
            raise

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
