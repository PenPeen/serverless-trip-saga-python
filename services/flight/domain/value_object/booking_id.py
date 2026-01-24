from dataclasses import dataclass

from services.shared.domain import TripId


@dataclass(frozen=True)
class BookingId:
    """フライト予約ID（Value Object）

    不変で、値が同じなら同一とみなされる。
    """

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_trip_id(cls, trip_id: TripId) -> "BookingId":
        """TripId から冪等な BookingId を生成

        同じ TripId からは常に同じ BookingId が生成される。
        これにより、リトライ時の冪等性が担保される。
        """
        return cls(value=f"flight_for_{trip_id}")
