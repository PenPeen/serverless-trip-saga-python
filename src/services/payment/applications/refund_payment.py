from services.payment.domain.entity import Payment
from services.payment.domain.repository import PaymentRepository
from services.shared.domain import TripId


class RefundPaymentService:
    """払い戻しサービス（補償トランザクション用）"""

    def __init__(self, repository: PaymentRepository) -> None:
        self._repository = repository

    def refund(self, trip_id: TripId) -> Payment | None:
        """決済を払い戻す"""
        payment = self._repository.find_by_trip_id(trip_id)
        if payment is None:
            return None
        payment.refund()
        self._repository.update(payment)
        return payment
