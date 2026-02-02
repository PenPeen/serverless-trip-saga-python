from services.hotel.domain.value_object.hotel_booking_id import HotelBookingId
from services.shared.domain.value_object.trip_id import TripId


class TestHotelBookingId:
    def test_create_hotel_booking_id(self):
        booking_id = HotelBookingId(value="test-id")
        assert booking_id.value == "test-id"

    def test_str_returns_value(self):
        booking_id = HotelBookingId(value="test-id")
        assert str(booking_id) == "test-id"

    def test_from_trip_id(self):
        trip_id = TripId(value="trip-123")
        booking_id = HotelBookingId.from_trip_id(trip_id)
        assert booking_id.value == "hotel_for_trip-123"

    def test_from_trip_id_is_deterministic(self):
        trip_id = TripId(value="trip-456")
        booking_id_1 = HotelBookingId.from_trip_id(trip_id)
        booking_id_2 = HotelBookingId.from_trip_id(trip_id)
        assert booking_id_1 == booking_id_2
