from dataclasses import dataclass


@dataclass(frozen=True)
class TripId:
    """旅行ID（全サービス共通）

    Value Object として不変性を保証。
    同じ値を持つ TripId は同一とみなされる。
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("TripId cannot be empty")

    def __str__(self) -> str:
        return self.value
