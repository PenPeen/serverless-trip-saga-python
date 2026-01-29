from decimal import Decimal
from unittest.mock import MagicMock

from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.domain.entity.booking import Booking
from services.flight.domain.enum.booking_status import BookingStatus
from services.flight.domain.factory import BookingFactory
from services.flight.domain.factory.booking_factory import FlightDetails
from services.shared.domain.value_object.trip_id import TripId


class TestReserveFlightService:
    """ReserveFlightService のテスト"""

    def test_reserve_create_and_saves_booking(self):
        """予約が作成され、Repository に保存され、Entity が返される"""

        # Arrange
        mock_repository = MagicMock()
        factory = BookingFactory()
        service = ReserveFlightService(repository=mock_repository, factory=factory)

        trip_id = TripId(value="trip-123")
        flight_details: FlightDetails = {
            "flight_number": "NH001",
            "departure_time": "2024-01-01T10:00:00",
            "arrival_time": "2024-01-01T12:00:00",
            "price_amount": Decimal("50000"),
            "price_currency": "JPY",
        }

        # Act
        booking = service.reserve(trip_id, flight_details)

        # Assert
        assert isinstance(booking, Booking)
        assert booking.trip_id == trip_id
        assert booking.status == BookingStatus.PENDING

        mock_repository.save.assert_called_once()
        saved_booking = mock_repository.save.call_args[0][0]
        assert saved_booking == booking
