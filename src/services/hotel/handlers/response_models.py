from __future__ import annotations

from pydantic import BaseModel

from services.hotel.domain.entity.hotel_booking import HotelBooking


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


def to_response(booking: HotelBooking) -> dict:
    """HotelBooking エンティティをレスポンス辞書に変換する"""
    return SuccessResponse(
        data=HotelBookingData(
            booking_id=str(booking.id),
            trip_id=str(booking.trip_id),
            hotel_name=str(booking.hotel_name),
            check_in_date=booking.stay_period.check_in,
            check_out_date=booking.stay_period.check_out,
            nights=booking.stay_period.nights(),
            price_amount=str(booking.price.amount),
            price_currency=str(booking.price.currency),
            status=booking.status.value,
        )
    ).model_dump()
