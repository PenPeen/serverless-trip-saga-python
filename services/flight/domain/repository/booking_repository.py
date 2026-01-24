from abc import abstractmethod
from typing import Optional

from services.flight.domain.entity import Booking
from services.flight.domain.value_object import BookingId
from services.shared.domain import Repository, TripId


class BookingRepository(Repository[Booking, BookingId]):
    """フライト予約リポジトリのインターフェース

    Domain 層で定義し、具象実装は Infrastructure 層で行う。
    これにより、Domain はインフラ（DynamoDB 等）に依存しない。
    """

    @abstractmethod
    def save(self, booking: Booking) -> None:
        """予約を保存する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, booking_id: BookingId) -> Optional[Booking]:
        """予約IDで検索する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: TripId) -> Optional[Booking]:
        """Trip ID で検索する（1 Trip = 1 Flight の前提）"""
        raise NotImplementedError
