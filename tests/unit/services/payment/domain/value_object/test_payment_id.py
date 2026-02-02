from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain.value_object.trip_id import TripId


class TestPaymentId:
    def test_create_payment_id(self):
        payment_id = PaymentId(value="test-id")
        assert payment_id.value == "test-id"

    def test_str_returns_value(self):
        payment_id = PaymentId(value="test-id")
        assert str(payment_id) == "test-id"

    def test_from_trip_id(self):
        trip_id = TripId(value="trip-123")
        payment_id = PaymentId.from_trip_id(trip_id)
        assert payment_id.value == "payment_for_trip-123"

    def test_from_trip_id_is_deterministic(self):
        trip_id = TripId(value="trip-456")
        payment_id_1 = PaymentId.from_trip_id(trip_id)
        payment_id_2 = PaymentId.from_trip_id(trip_id)
        assert payment_id_1 == payment_id_2
