from decimal import Decimal

from services.payment.domain.entity import Payment
from services.payment.domain.factory import PaymentFactory
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
        payment: Payment = self._factory.create(trip_id, amount, currency_code)
        payment.complete()
        self._repository.save(payment)
        return payment
