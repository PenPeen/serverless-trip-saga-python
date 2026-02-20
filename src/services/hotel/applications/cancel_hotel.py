from services.hotel.domain.entity import HotelBooking
from services.hotel.domain.repository import HotelBookingRepository
from services.shared.domain import TripId


class CancelHotelService:
    """ホテル予約キャンセルサービス（補償トランザクション用）"""

    def __init__(self, repository: HotelBookingRepository) -> None:
        self._repository = repository

    def cancel(self, trip_id: TripId) -> HotelBooking | None:
        """ホテル予約をキャンセルする"""
        booking = self._repository.find_by_trip_id(trip_id)
        if booking is None:
            return None
        expected_status = booking.status
        booking.cancel()
        self._repository.update(booking, expected_status=expected_status)
        return booking
