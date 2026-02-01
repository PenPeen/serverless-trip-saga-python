from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ProcessPaymentRequest(BaseModel):
    """決済処理リクエストモデル"""

    trip_id: str = Field(..., min_length=1)
    amount: Decimal = Field(
        ...,
        gt=0,
        description="決済金額（0より大きい値）",
    )
    currency: str = Field(
        default="JPY",
        pattern="^[A-Z]{3}$",
        description="通貨コード（ISO 4217）",
    )

    @field_validator("amount", mode="before")
    @classmethod
    def convert_amount_to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class RefundPaymentRequest(BaseModel):
    """払い戻しリクエストモデル（補償トランザクション用）"""

    trip_id: str = Field(..., min_length=1)
