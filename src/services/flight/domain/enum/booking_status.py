from enum import Enum


class BookingStatus(str, Enum):
    """予約ステータス"""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
