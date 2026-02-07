from decimal import Decimal

from services.hotel.applications.reserve_hotel import ReserveHotelService
from services.hotel.domain.entity.hotel_booking import HotelBooking
from services.hotel.domain.enum.hotel_booking_status import HotelBookingStatus
from services.hotel.domain.factory.hotel_booking_factory import (
    HotelBookingFactory,
    HotelDetails,
)


class TestReserveHotelService:
    def test_reserve_creates_and_saves_booking(self, mock_repository, trip_id):
        factory = HotelBookingFactory()
        service = ReserveHotelService(repository=mock_repository, factory=factory)
        hotel_details: HotelDetails = {
            "hotel_name": "Grand Hotel",
            "check_in_date": "2024-01-01",
            "check_out_date": "2024-01-03",
            "price_amount": Decimal("30000"),
            "price_currency": "JPY",
        }

        booking = service.reserve(trip_id, hotel_details)

        assert isinstance(booking, HotelBooking)
        assert booking.trip_id == trip_id
        assert booking.status == HotelBookingStatus.PENDING
        mock_repository.save.assert_called_once()
        saved_booking = mock_repository.save.call_args[0][0]
        assert saved_booking == booking
