from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain import AggregateRoot, Money, TripId
from services.shared.domain.exception import BusinessRuleViolationException


class Payment(AggregateRoot[PaymentId]):
    """決済エンティティ"""

    def __init__(
        self,
        id: PaymentId,
        trip_id: TripId,
        amount: Money,
        status: PaymentStatus = PaymentStatus.PENDING,
    ) -> None:
        super().__init__(id)
        self._trip_id = trip_id
        self._amount = amount
        self._status = status

    @property
    def trip_id(self) -> TripId:
        return self._trip_id

    @property
    def amount(self) -> Money:
        return self._amount

    @property
    def status(self) -> PaymentStatus:
        return self._status

    def complete(self) -> None:
        """決済を完了する"""
        if self._status != PaymentStatus.PENDING:
            raise BusinessRuleViolationException(
                f"Cannot complete payment in {self._status} status"
            )
        self._status = PaymentStatus.COMPLETED

    def refund(self) -> None:
        """払い戻しを行う（補償トランザクション用）"""
        if self._status == PaymentStatus.REFUNDED:
            return
        if self._status != PaymentStatus.COMPLETED:
            raise BusinessRuleViolationException("Can only refund completed payments")
        self._status = PaymentStatus.REFUNDED
