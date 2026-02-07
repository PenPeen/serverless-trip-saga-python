from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class Currency:
    """通貨コード（ISO 4217）

    サポート対象: JPY, USD
    """

    SUPPORTED: ClassVar[frozenset[str]] = frozenset({"JPY", "USD"})

    code: str

    def __post_init__(self) -> None:
        normalized = self.code.upper()
        if normalized not in self.SUPPORTED:
            raise ValueError(
                f"Unsupported currency: {self.code}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED))}"
            )
        object.__setattr__(self, "code", normalized)

    def __str__(self) -> str:
        return self.code

    @classmethod
    def jpy(cls) -> Currency:
        """日本円"""
        return cls("JPY")

    @classmethod
    def usd(cls) -> Currency:
        """米ドル"""
        return cls("USD")
