from __future__ import annotations

from dataclasses import dataclass

from services.shared.domain.value_object.trip_id import TripId


@dataclass(frozen=True)
class PaymentId:
    """決済ID"""

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_trip_id(cls, trip_id: TripId) -> PaymentId:
        """TripId から冪等な PaymentId を生成"""
        return cls(value=f"payment_for_{trip_id}")
