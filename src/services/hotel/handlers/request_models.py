from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class HotelDetailsRequest(BaseModel):
    """ホテル詳細のリクエストモデル"""

    hotel_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="ホテル名",
    )
    check_in_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="チェックイン日（YYYY-MM-DD形式）",
        examples=["2024-01-01"],
    )
    check_out_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="チェックアウト日（YYYY-MM-DD形式）",
        examples=["2024-01-03"],
    )
    price_amount: Decimal = Field(
        ...,
        gt=0,
        description="料金",
    )
    price_currency: str = Field(
        default="JPY",
        pattern="^[A-Z]{3}$",
        description="通貨コード（ISO 4217）",
    )

    @field_validator("price_amount", mode="before")
    @classmethod
    def convert_price_to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class ReserveHotelRequest(BaseModel):
    """ホテル予約リクエストモデル"""

    trip_id: str = Field(..., min_length=1)
    hotel_details: HotelDetailsRequest


class CancelHotelRequest(BaseModel):
    """ホテルキャンセルリクエストモデル（補償トランザクション用）"""

    trip_id: str = Field(..., min_length=1)
