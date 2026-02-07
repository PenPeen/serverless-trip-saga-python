from dataclasses import dataclass


@dataclass(frozen=True)
class TripId:
    """旅行ID"""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("TripId cannot be empty")

    def __str__(self) -> str:
        return self.value
