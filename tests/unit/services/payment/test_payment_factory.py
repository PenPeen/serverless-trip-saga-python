from decimal import Decimal

from services.payment.domain.entity.payment import Payment
from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.factory.payment_factory import PaymentFactory
from services.shared.domain import TripId


class TestPaymentFactory:
    def test_create_payment(self):
        factory = PaymentFactory()
        trip_id = TripId(value="trip-123")

        payment = factory.create(
            trip_id=trip_id,
            amount=Decimal("50000"),
            currency_code="JPY",
        )

        assert isinstance(payment, Payment)
        assert payment.trip_id == trip_id
        assert payment.status == PaymentStatus.PENDING
        assert payment.id.value == "payment_for_trip-123"
