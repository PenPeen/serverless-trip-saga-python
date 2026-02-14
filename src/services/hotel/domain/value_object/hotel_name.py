from dataclasses import dataclass


@dataclass(frozen=True)
class HotelName:
    """ホテル名"""

    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value.strip()) == 0:
            raise ValueError("Hotel name cannot be empty")
        if len(self.value) > 100:
            raise ValueError("Hotel name is too long (max 100 characters)")

    def __str__(self) -> str:
        return self.value
