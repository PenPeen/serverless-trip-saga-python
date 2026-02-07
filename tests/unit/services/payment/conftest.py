from decimal import Decimal

import pytest

from services.payment.domain.entity.payment import Payment
from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain import Currency, Money, TripId


@pytest.fixture
def create_payment():
    """Payment を生成する Factory fixture（Factories as fixtures パターン）"""

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
