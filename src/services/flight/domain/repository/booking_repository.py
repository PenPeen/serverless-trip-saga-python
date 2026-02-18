from abc import abstractmethod

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
    def find_by_id(self, booking_id: BookingId) -> Booking | None:
        """予約IDで検索"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: TripId) -> Booking | None:
        """TripIDで検索"""
        raise NotImplementedError

    @abstractmethod
    def update(self, booking: Booking) -> None:
        """予約を更新する"""
        raise NotImplementedError
