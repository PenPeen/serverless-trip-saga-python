from decimal import Decimal

from services.payment.domain.entity import Payment
from services.payment.domain.factory import PaymentFactory
from services.payment.domain.factory.payment_factory import PaymentDetails
from services.payment.domain.repository import PaymentRepository
from services.shared.domain import TripId


class ProcessPaymentService:
    """決済処理ユースケース"""

    def __init__(
        self,
        repository: PaymentRepository,
        factory: PaymentFactory,
    ) -> None:
        self._repository = repository
        self._factory = factory

    def process(
        self,
        trip_id: TripId,
        amount: Decimal,
        currency_code: str,
    ) -> Payment:
        """決済を処理する"""
        payment_details: PaymentDetails = {
            "amount": amount,
            "currency_code": currency_code,
        }
        payment: Payment = self._factory.create(trip_id, payment_details)
        payment.complete()
        self._repository.save(payment)
        return payment
