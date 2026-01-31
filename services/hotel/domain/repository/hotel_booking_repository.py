from abc import abstractmethod
from typing import Optional

from services.hotel.domain.entity.hotel_booking import HotelBooking
from services.hotel.domain.value_object.hotel_booking_id import HotelBookingId
from services.shared.domain import Repository, TripId


class HotelBookingRepository(Repository[HotelBooking, HotelBookingId]):
    """ホテル予約レポジトリのインターフェース"""

    @abstractmethod
    def save(self, booking: HotelBooking) -> None:
        """予約を保存する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, booking_id: HotelBookingId) -> Optional[HotelBooking]:
        """予約IDで検索する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: TripId) -> Optional[HotelBooking]:
        """TripIDで検索する"""
        raise NotImplementedError
