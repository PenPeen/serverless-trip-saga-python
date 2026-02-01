from decimal import Decimal

from services.payment.domain.entity.payment import Payment
from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain.value_object.currency import Currency
from services.shared.domain.value_object.money import Money
from services.shared.domain.value_object.trip_id import TripId


class PaymentFactory:
    """決済ファクトリ"""

    def create(
        self,
        trip_id: TripId,
        amount: Decimal,
        currency_code: str,
    ) -> Payment:
        """新規決済エンティティを生成する"""
        payment_id = PaymentId.from_trip_id(trip_id)

        money = Money(amount=amount, currency=Currency(currency_code))

        return Payment(
            id=payment_id,
            trip_id=trip_id,
            amount=money,
            status=PaymentStatus.PENDING,
        )
