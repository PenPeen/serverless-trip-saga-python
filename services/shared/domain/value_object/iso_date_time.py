from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IsoDateTime:
    """日時(ISO 8601形式)"""

    value: datetime

    @classmethod
    def from_string(cls, s: str) -> IsoDateTime:
        """ISO 8601 形式の文字列から生成"""
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO 8601 datetime: {s}") from e
        return cls(value=dt)

    def __str__(self):
        return self.value

    def is_before(self, other: IsoDateTime) -> bool:
        """他の日時より前かどうか"""
        return self.value < other.value

    def is_after(self, other: IsoDateTime) -> bool:
        """他の日時より後かどうか"""
        return self.value > other.value
