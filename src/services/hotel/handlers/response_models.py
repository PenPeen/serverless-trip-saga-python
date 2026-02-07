from pydantic import BaseModel


class HotelBookingData(BaseModel):
    """ホテル予約データのレスポンスモデル"""

    booking_id: str
    trip_id: str
    hotel_name: str
    check_in_date: str
    check_out_date: str
    nights: int
    price_amount: str
    price_currency: str
    status: str


class SuccessResponse(BaseModel):
    """成功レスポンスモデル"""

    status: str = "success"
    data: HotelBookingData


class ErrorResponse(BaseModel):
    """エラーレスポンスモデル"""

    status: str = "error"
    error_code: str
    message: str
    details: list | None = None
