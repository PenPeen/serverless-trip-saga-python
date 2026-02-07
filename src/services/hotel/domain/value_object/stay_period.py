from dataclasses import dataclass
from datetime import date
from functools import cached_property


@dataclass(frozen=True)
class StayPeriod:
    """滞在期間(チェックイン日 + チェックアウト日)"""

    check_in: str
    check_out: str

    def __post_init__(self) -> None:
        try:
            check_in_date = self._check_in_date
            check_out_date = self._check_out_date
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}") from e

        if check_out_date <= check_in_date:
            raise ValueError("Check-out date must be after check-in date")

    @cached_property
    def _check_in_date(self) -> date:
        return date.fromisoformat(self.check_in)

    @cached_property
    def _check_out_date(self) -> date:
        return date.fromisoformat(self.check_out)

    def nights(self) -> int:
        """宿泊数を計算する"""
        check_in_date = self._check_in_date
        check_out_date = self._check_out_date

        return (check_out_date - check_in_date).days
