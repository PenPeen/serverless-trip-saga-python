from decimal import Decimal

import pytest

from services.hotel.domain.entity.hotel_booking import HotelBooking
from services.hotel.domain.enum.hotel_booking_status import HotelBookingStatus
from services.hotel.domain.value_object.hotel_booking_id import HotelBookingId
from services.hotel.domain.value_object.hotel_name import HotelName
from services.hotel.domain.value_object.stay_period import StayPeriod
from services.shared.domain import Currency, Money, TripId
from services.shared.domain.exception.exceptions import BusinessRuleViolationException


class TestHotelBooking:
    @pytest.fixture
    def create_booking(self):
        def _factory(
            status: HotelBookingStatus = HotelBookingStatus.PENDING,
            booking_id: str = "test-id",
            trip_id: str = "trip-123",
            hotel_name: str = "Grand Hotel",
            check_in: str = "2024-01-01",
            check_out: str = "2024-01-03",
            price_amount: Decimal = Decimal("30000"),
        ) -> HotelBooking:
            return HotelBooking(
                id=HotelBookingId(value=booking_id),
                trip_id=TripId(value=trip_id),
                hotel_name=HotelName(value=hotel_name),
                stay_period=StayPeriod(check_in=check_in, check_out=check_out),
                price=Money(amount=price_amount, currency=Currency.jpy()),
                status=status,
            )

        return _factory

    def test_confirm_pending_booking(self, create_booking):
        booking = create_booking(status=HotelBookingStatus.PENDING)
        booking.confirm()
        assert booking.status == HotelBookingStatus.CONFIRMED

    def test_cannot_confirm_cancelled_booking(self, create_booking):
        booking = create_booking(status=HotelBookingStatus.CANCELED)
        with pytest.raises(BusinessRuleViolationException):
            booking.confirm()

    def test_cancel_pending_booking(self, create_booking):
        booking = create_booking(status=HotelBookingStatus.PENDING)
        booking.cancel()
        assert booking.status == HotelBookingStatus.CANCELED

    def test_cancel_confirmed_booking(self, create_booking):
        booking = create_booking(status=HotelBookingStatus.CONFIRMED)
        booking.cancel()
        assert booking.status == HotelBookingStatus.CANCELED

    def test_cancel_already_cancelled_booking(self, create_booking):
        booking = create_booking(status=HotelBookingStatus.CANCELED)
        booking.cancel()
        assert booking.status == HotelBookingStatus.CANCELED

    def test_booking_properties(self, create_booking):
        booking = create_booking()
        assert booking.trip_id == TripId(value="trip-123")
        assert booking.hotel_name == HotelName(value="Grand Hotel")
        assert booking.status == HotelBookingStatus.PENDING
