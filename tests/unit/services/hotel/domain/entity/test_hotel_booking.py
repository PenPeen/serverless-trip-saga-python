import pytest

from services.hotel.domain.enum.hotel_booking_status import HotelBookingStatus
from services.hotel.domain.value_object.hotel_name import HotelName
from services.shared.domain import TripId
from services.shared.domain.exception.exceptions import BusinessRuleViolationException


class TestHotelBooking:
    def test_confirm_pending_booking(self, create_hotel_booking):
        booking = create_hotel_booking(status=HotelBookingStatus.PENDING)
        booking.confirm()
        assert booking.status == HotelBookingStatus.CONFIRMED

    def test_cannot_confirm_cancelled_booking(self, create_hotel_booking):
        booking = create_hotel_booking(status=HotelBookingStatus.CANCELED)
        with pytest.raises(BusinessRuleViolationException):
            booking.confirm()

    def test_cancel_pending_booking(self, create_hotel_booking):
        booking = create_hotel_booking(status=HotelBookingStatus.PENDING)
        booking.cancel()
        assert booking.status == HotelBookingStatus.CANCELED

    def test_cancel_confirmed_booking(self, create_hotel_booking):
        booking = create_hotel_booking(status=HotelBookingStatus.CONFIRMED)
        booking.cancel()
        assert booking.status == HotelBookingStatus.CANCELED

    def test_cancel_already_cancelled_booking(self, create_hotel_booking):
        booking = create_hotel_booking(status=HotelBookingStatus.CANCELED)
        booking.cancel()
        assert booking.status == HotelBookingStatus.CANCELED

    def test_booking_properties(self, create_hotel_booking):
        booking = create_hotel_booking()
        assert booking.trip_id == TripId(value="trip-123")
        assert booking.hotel_name == HotelName(value="Grand Hotel")
        assert booking.status == HotelBookingStatus.PENDING
