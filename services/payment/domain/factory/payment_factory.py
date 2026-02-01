from decimal import Decimal

from services.payment.domain.entity.payment import Payment
from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain.value_object.currency import Currency
from services.shared.domain.value_object.money import Money
from services.shared.domain.value_object.trip_id import TripId


class PaymentFactory:
    """決済ファクトリ

    - 冪等性を担保する ID 生成
    - プリミティブ型から Value Object への変換
    """

    def create(
        self,
        trip_id: TripId,
        amount: Decimal,
        currency_code: str,
    ) -> Payment:
        """新規決済エンティティを生成する"""
        # 冪等性担保: 同じ TripId からは常に同じ PaymentId を生成
        payment_id = PaymentId.from_trip_id(trip_id)

        # プリミティブ型から Value Object に変換
        money = Money(amount=amount, currency=Currency(currency_code))

        return Payment(
            id=payment_id,
            trip_id=trip_id,
            amount=money,
            status=PaymentStatus.PENDING,
        )
