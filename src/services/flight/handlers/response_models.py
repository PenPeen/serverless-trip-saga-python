from __future__ import annotations

from pydantic import BaseModel

from services.flight.domain.entity.booking import Booking


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


def to_response(booking: Booking) -> dict:
    """Booking エンティティをレスポンス辞書に変換する"""
    return SuccessResponse(
        data=BookingData(
            booking_id=str(booking.id),
            trip_id=str(booking.trip_id),
            flight_number=str(booking.flight_number),
            departure_time=str(booking.departure_time),
            arrival_time=str(booking.arrival_time),
            price_amount=str(booking.price.amount),
            price_currency=str(booking.price.currency),
            status=booking.status.value,
        )
    ).model_dump()
