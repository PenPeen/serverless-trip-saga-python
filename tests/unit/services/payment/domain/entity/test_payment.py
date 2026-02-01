from decimal import Decimal

import pytest

from services.payment.domain.entity.payment import Payment
from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain import Currency, Money, TripId
from services.shared.domain.exception.exceptions import BusinessRuleViolationException


class TestPayment:
    @pytest.fixture
    def create_payment(self):
        def _factory(
            status: PaymentStatus = PaymentStatus.PENDING,
            payment_id: str = "test-id",
            trip_id: str = "trip-123",
            amount: Decimal = Decimal("50000"),
        ) -> Payment:
            return Payment(
                id=PaymentId(value=payment_id),
                trip_id=TripId(value=trip_id),
                amount=Money(amount=amount, currency=Currency.jpy()),
                status=status,
            )

        return _factory

    def test_complete_pending_payment(self, create_payment):
        payment = create_payment(status=PaymentStatus.PENDING)
        payment.complete()
        assert payment.status == PaymentStatus.COMPLETED

    def test_cannot_complete_completed_payment(self, create_payment):
        payment = create_payment(status=PaymentStatus.COMPLETED)
        with pytest.raises(BusinessRuleViolationException):
            payment.complete()

    def test_cannot_complete_refunded_payment(self, create_payment):
        payment = create_payment(status=PaymentStatus.REFUNDED)
        with pytest.raises(BusinessRuleViolationException):
            payment.complete()

    def test_refund_completed_payment(self, create_payment):
        payment = create_payment(status=PaymentStatus.COMPLETED)
        payment.refund()
        assert payment.status == PaymentStatus.REFUNDED

    def test_refund_is_idempotent(self, create_payment):
        payment = create_payment(status=PaymentStatus.REFUNDED)
        payment.refund()
        assert payment.status == PaymentStatus.REFUNDED

    def test_cannot_refund_pending_payment(self, create_payment):
        payment = create_payment(status=PaymentStatus.PENDING)
        with pytest.raises(BusinessRuleViolationException):
            payment.refund()

    def test_payment_properties(self, create_payment):
        payment = create_payment()
        assert payment.trip_id == TripId(value="trip-123")
        assert payment.amount == Money(amount=Decimal("50000"), currency=Currency.jpy())
        assert payment.status == PaymentStatus.PENDING
