import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class FlightNumber:
    """フライト番号

    航空会社コード（2文字）+ 便名番号（1-4桁）の形式。
    例: NH001, JL123, AA1234
    """

    value: str

    # フライト番号の形式: 2文字の航空会社コード + 1-4桁の数字
    PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Z]{2}\d{1,4}$")

    def __post_init__(self) -> None:
        normalized = self.value.upper()
        if not self.PATTERN.match(normalized):
            raise ValueError(
                f"Invalid flight number format: {self.value}. "
                "Expected format: AA123 (2 letters + 1-4 digits)"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value

    @property
    def airline_code(self) -> str:
        """航空会社コード（冒頭2文字）"""
        return self.value[:2]

    @property
    def flight_num(self) -> str:
        """便名番号"""
        return self.value[2:]
