from dataclasses import dataclass
from decimal import Decimal

from .currency import Currency


@dataclass(frozen=True)
class Money:
    """金額（通貨情報を含む）

    Value Object として不変性を保証。
    金額の演算メソッドを提供。
    """

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"

    def add(self, other: "Money") -> "Money":
        """金額を加算する"""
        if self.currency != other.currency:
            raise ValueError("Cannot add money with different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    @classmethod
    def jpy(cls, amount: Decimal | int | str) -> "Money":
        """日本円で Money を生成"""
        return cls(amount=Decimal(str(amount)), currency=Currency.jpy())
