from services.flight.domain.entity import Booking
from services.flight.domain.repository import BookingRepository
from services.shared.domain import TripId


class CancelFlightService:
    """フライト予約キャンセルサービス（補償トランザクション用）"""

    def __init__(self, repository: BookingRepository) -> None:
        self._repository = repository

    def cancel(self, trip_id: TripId) -> Booking | None:
        """フライト予約をキャンセルする"""
        booking = self._repository.find_by_trip_id(trip_id)
        if booking is None:
            return None
        expected_status = booking.status
        booking.cancel()
        self._repository.update(booking, expected_status=expected_status)
        return booking
