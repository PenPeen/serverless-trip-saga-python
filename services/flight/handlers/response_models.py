from pydantic import BaseModel


class BookingData(BaseModel):
    """予約データのレスポンスモデル"""

    booking_id: str
    trip_id: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price_amount: str
    price_currency: str
    status: str


class SuccessResponse(BaseModel):
    """成功レスポンスモデル"""

    status: str = "success"
    data: BookingData


class ErrorResponse(BaseModel):
    """エラーレスポンスモデル"""

    status: str = "error"
    error_code: str
    message: str
    details: list | None = None
