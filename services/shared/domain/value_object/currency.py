from dataclasses import dataclass


@dataclass(frozen=True)
class Currency:
    """通貨コード（ISO 4217）

    例: JPY, USD, EUR
    """

    code: str

    def __post_init__(self) -> None:
        if len(self.code) != 3 or not self.code.isalpha():
            raise ValueError(f"Invalid currency code: {self.code}")
        # frozen=True でも __post_init__ 内では object.__setattr__ が必要
        object.__setattr__(self, "code", self.code.upper())

    def __str__(self) -> str:
        return self.code

    @classmethod
    def jpy(cls) -> "Currency":
        """日本円"""
        return cls("JPY")

    @classmethod
    def usd(cls) -> "Currency":
        """米ドル"""
        return cls("USD")
