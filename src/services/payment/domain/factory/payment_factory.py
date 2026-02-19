from decimal import Decimal
from typing import TypedDict

from services.payment.domain.entity.payment import Payment
from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain import Currency, Money, TripId


class PaymentDetails(TypedDict):
    """決済の入力データ構造（TypedDict）"""

    amount: Decimal
    currency_code: str


class PaymentFactory:
    """決済ファクトリ"""

    def create(
        self,
        trip_id: TripId,
        payment_details: PaymentDetails,
    ) -> Payment:
        """新規決済エンティティを生成する"""
        payment_id = PaymentId.from_trip_id(trip_id)

        money = Money(
            amount=payment_details["amount"],
            currency=Currency(payment_details["currency_code"]),
        )

        return Payment(
            id=payment_id,
            trip_id=trip_id,
            amount=money,
            status=PaymentStatus.PENDING,
        )
