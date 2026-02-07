from abc import abstractmethod
from typing import Optional

from services.flight.domain.entity import Booking
from services.flight.domain.value_object import BookingId
from services.shared.domain import Repository, TripId


class BookingRepository(Repository[Booking, BookingId]):
    """フライト予約レポジトリ"""

    @abstractmethod
    def save(self, booking: Booking) -> None:
        """永続化する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, booking_id: BookingId) -> Optional[Booking]:
        """予約IDで検索"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, tripId: TripId) -> Optional[Booking]:
        """TripIDで検索"""
        raise NotImplementedError
