from decimal import Decimal

from services.hotel.domain.entity.hotel_booking import HotelBooking
from services.hotel.domain.enum.hotel_booking_status import HotelBookingStatus
from services.hotel.domain.factory.hotel_booking_factory import (
    HotelBookingFactory,
    HotelDetails,
)


class TestHotelBookingFactory:
    def test_create_hotel_booking(self, trip_id):
        factory = HotelBookingFactory()
        hotel_details: HotelDetails = {
            "hotel_name": "Grand Hotel",
            "check_in_date": "2024-01-01",
            "check_out_date": "2024-01-03",
            "price_amount": Decimal("30000"),
            "price_currency": "JPY",
        }

        booking = factory.create(trip_id, hotel_details)

        assert isinstance(booking, HotelBooking)
        assert booking.trip_id == trip_id
        assert booking.status == HotelBookingStatus.PENDING
        assert booking.id.value == "hotel_for_trip-123"
