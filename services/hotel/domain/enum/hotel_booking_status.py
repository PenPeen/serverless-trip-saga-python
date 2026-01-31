from enum import Enum


class HotelBookingStatus(str, Enum):
    """ホテル予約ステータス"""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"
