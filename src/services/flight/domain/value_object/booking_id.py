from __future__ import annotations

from dataclasses import dataclass

from services.shared.domain import TripId


@dataclass(frozen=True)
class BookingId:
    """フライト予約ID

    例: "flight_for_trip-123"
    """

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_trip_id(cls, trip_id: TripId) -> BookingId:
        """TripId から冪等な BookingIdを生成"""

        return cls(value=f"flight_for_#{trip_id}")
