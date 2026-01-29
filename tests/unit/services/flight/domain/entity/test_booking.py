from decimal import Decimal

import pytest

from services.flight.domain.entity import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.value_object import BookingId, FlightNumber
from services.shared.domain import Currency, IsoDateTime, Money, TripId
from services.shared.domain.exception.exceptions import BusinessRuleViolationException


class TestBooking:
    """Booking Entity のテスト"""

    @pytest.fixture
    def create_booking(self):
        """Bookingを生成するFactoryを返す"""

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

    def test_confirm_pending_booking(self, create_booking):
        """PENDING状態の予約をconfirmするとCONFIRMED状態になる"""
        booking = create_booking(status=BookingStatus.PENDING)
        booking.confirm()
        assert booking.status == BookingStatus.CONFIRMED

    def test_cannnot_confirm_cancelled_booking(self, create_booking):
        """CANCELD状態の予約をconfirmすると BusinessRuleViolationException が発生する"""
        booking = create_booking(status=BookingStatus.CANCELLED)
        with pytest.raises(BusinessRuleViolationException):
            booking.confirm()

    def tset_invalid_shecule_raises_erorr(self):
        """出発時刻よりも到着時刻が前の場合、例外が発生する"""
        departure_time = IsoDateTime.from_string("2024-01-01T12:00:00")
        arrival_time = IsoDateTime.from_string("2024-01-01T10:00:00")

        with pytest.raises(BusinessRuleViolationException):
            Booking(
                id=BookingId(value="test-id"),
                trip_id=TripId(value="trip-123"),
                flight_number=FlightNumber(value="NH001"),
                departure_time=departure_time,
                arrival_time=arrival_time,
                price=Money(amount=Decimal("50000"), currency=Currency.jpy()),
            )
