from decimal import Decimal

import pytest

from services.flight.domain.entity import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.value_object import BookingId, FlightNumber
from services.shared.domain import Currency, IsoDateTime, Money, TripId


@pytest.fixture
def create_booking():
    """Booking を生成する Factory fixture（Factories as fixtures パターン）"""

    def _factory(
        status: BookingStatus = BookingStatus.PENDING,
        booking_id: str = "test-id",
        trip_id: str = "trip-123",
        flight_number: str = "NH001",
        departure_time: str = "2024-01-01T10:00:00",
        arrival_time: str = "2024-01-01T12:00:00",
        price_amount: Decimal = Decimal("50000"),
    ) -> Booking:
        return Booking(
            id=BookingId(value=booking_id),
            trip_id=TripId(value=trip_id),
            flight_number=FlightNumber(value=flight_number),
            departure_time=IsoDateTime.from_string(departure_time),
            arrival_time=IsoDateTime.from_string(arrival_time),
            price=Money(amount=price_amount, currency=Currency.jpy()),
            status=status,
        )

    return _factory
