from __future__ import annotations

from dataclasses import dataclass

from services.shared.domain.value_object.trip_id import TripId


@dataclass(frozen=True)
class HotelBookingId:
    """ホテル予約ID"""

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_trip_id(cls, trip_id: TripId) -> HotelBookingId:
        """TripID から HotelBookingID を生成する"""

        return cls(value=f"hotel_for_{trip_id}")
