from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DateTime:
    """日時（ISO 8601 形式）

    Value Object として不変性を保証。
    日時の比較や変換メソッドを提供。
    """

    value: str

    def __post_init__(self) -> None:
        # ISO 8601 形式のバリデーション
        try:
            datetime.fromisoformat(self.value.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO 8601 datetime: {self.value}") from e

    def __str__(self) -> str:
        return self.value

    def to_datetime(self) -> datetime:
        """datetime オブジェクトに変換"""
        return datetime.fromisoformat(self.value.replace("Z", "+00:00"))

    def is_before(self, other: "DateTime") -> bool:
        """他の日時より前かどうか"""
        return self.to_datetime() < other.to_datetime()

    def is_after(self, other: "DateTime") -> bool:
        """他の日時より後かどうか"""
        return self.to_datetime() > other.to_datetime()
