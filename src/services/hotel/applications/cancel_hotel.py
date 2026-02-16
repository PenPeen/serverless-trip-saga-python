from services.hotel.domain.entity.hotel_booking import HotelBooking
from services.hotel.domain.repository.hotel_booking_repository import (
    HotelBookingRepository,
)
from services.shared.domain.value_object.trip_id import TripId


class CancelHotelService:
    """ホテル予約キャンセルサービス（補償トランザクション用）"""

    def __init__(self, repository: HotelBookingRepository) -> None:
        self._repository = repository

    def cancel(self, trip_id: TripId) -> HotelBooking | None:
        """ホテル予約をキャンセルする"""
        booking = self._repository.find_by_trip_id(trip_id)
        if booking is None:
            return None
        booking.cancel()
        self._repository.update(booking)
        return booking
