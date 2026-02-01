from decimal import Decimal
from unittest.mock import MagicMock

from services.payment.applications.process_payment import ProcessPaymentService
from services.payment.domain.entity.payment import Payment
from services.payment.domain.enum.payment_status import PaymentStatus
from services.payment.domain.factory.payment_factory import PaymentFactory
from services.shared.domain import TripId


class TestProcessPaymentService:
    def test_process_creates_completes_and_saves_payment(self):
        mock_repository = MagicMock()
        factory = PaymentFactory()
        service = ProcessPaymentService(
            repository=mock_repository, factory=factory
        )
        trip_id = TripId(value="trip-123")

        payment = service.process(
            trip_id=trip_id,
            amount=Decimal("50000"),
            currency_code="JPY",
        )

        assert isinstance(payment, Payment)
        assert payment.trip_id == trip_id
        assert payment.status == PaymentStatus.COMPLETED
        mock_repository.save.assert_called_once()
        saved_payment = mock_repository.save.call_args[0][0]
        assert saved_payment == payment
