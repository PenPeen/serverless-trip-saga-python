import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from services.payment.domain.entity import Payment
from services.payment.domain.enum import PaymentStatus
from services.payment.domain.repository import PaymentRepository
from services.payment.domain.value_object import PaymentId
from services.shared.domain import Currency, Money, TripId
from services.shared.domain.exception.exceptions import DuplicateResourceException


class DynamoDBPaymentRepository(PaymentRepository):
    """DynamoDBを使用したPaymentRepository の具象実装"""

    def __init__(self, table_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("TABLE_NAME")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def save(self, payment: Payment) -> None:
        """決済をDBに保存する"""
        item = {
            "PK": f"TRIP#{payment.trip_id}",
            "SK": f"PAYMENT#{payment.id}",
            "entity_type": "PAYMENT",
            "payment_id": str(payment.id),
            "trip_id": str(payment.trip_id),
            "amount": str(payment.amount.amount),
            "currency": str(payment.amount.currency),
            "status": payment.status.value,
            "GSI1PK": "TRIPS",
            "GSI1SK": f"TRIP#{payment.trip_id}",
        }
        try:
            self.table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(PK)"
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateResourceException(
                    f"Payment already exists: {payment.id}"
                )

    def find_by_id(self, payment_id: PaymentId) -> Payment | None:
        """決済IDで検索"""
        response = self.table.scan(
            FilterExpression="payment_id = :pid",
            ExpressionAttributeValues={":pid": str(payment_id)},
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_entity(items[0])

    def find_by_trip_id(self, trip_id: TripId) -> Payment | None:
        """Trip ID で決済を検索する"""
        response = self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"TRIP#{trip_id}",
                ":sk_prefix": "PAYMENT#",
            },
        )
        items = response.get("Items", [])
        if not items:
            return None
        return self._to_entity(items[0])

    def _to_entity(self, item: dict) -> Payment:
        """DynamoDB アイテムをドメインエンティティに変換する"""
        return Payment(
            id=PaymentId(value=item["payment_id"]),
            trip_id=TripId(value=item["trip_id"]),
            amount=Money(
                amount=Decimal(item["amount"]),
                currency=Currency(item["currency"]),
            ),
            status=PaymentStatus(item["status"]),
        )
