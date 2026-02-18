from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class FlightDetailsRequest(BaseModel):
    """フライト詳細の入力スキーマ"""

    flight_number: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="フライト番号",
        examples=["NH001", "JL123"],
    )

    departure_time: str = Field(
        ...,
        description="出発時刻（ISO 8601形式）",
        examples=["2025-01-01T10:00:00"],
    )

    arrival_time: str = Field(
        ...,
        description="到着時刻（ISO 8601形式）",
        examples=["2025-01-01T12:00:00"],
    )

    price_amount: Decimal = Field(..., gt=0, description="料金", examples=[50000])

    price_currency: str = Field(
        default="JPY",
        patern="^[A-Z]{3}$",
        description="通貨コード（ISO 4217）",
        examples=["JPY", "USD"],
    )

    @field_validator("price_amount", mode="before")
    @classmethod
    def convert_price_to_decimal(cls, v):
        """Decimalに変換する"""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class ReserveFlightRequest(BaseModel):
    """フライト予約リクエストスキーマ"""

    trip_id: str = Field(
        ...,
        min_length=1,
        description="旅行ID",
        examples=["trip-123"],
    )

    flight_details: FlightDetailsRequest

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "trip_id": "trip-123",
                    "flight_details": {
                        "flight_number": "NH001",
                        "departure_time": "2024-01-01T10:00:00",
                        "arrival_time": "2024-01-01T12:00:00",
                        "price_amount": 50000,
                        "price_currency": "JPY",
                    },
                }
            ]
        }
    }


class CancelFlightRequest(BaseModel):
    """フライトキャンセルリクエストモデル（補償トランザクション用）"""

    trip_id: str = Field(..., min_length=1)
