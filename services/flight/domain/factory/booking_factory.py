from decimal import Decimal
from typing import TypedDict

from services.flight.domain.entity import Booking
from services.flight.domain.value_object import BookingId, BookingStatus, FlightNumber
from services.shared.domain import Currency, DateTime, Money, TripId


class FlightDetails(TypedDict):
    """フライト詳細の入力データ構造"""

    flight_number: str
    departure_time: str
    arrival_time: str
    price_amount: Decimal
    price_currency: str


class BookingFactory:
    """フライト予約エンティティのファクトリ

    - 冪等性を担保する ID 生成
    - プリミティブ型から Value Object への変換
    - 初期状態の設定
    """

    def create(self, trip_id: TripId, flight_details: FlightDetails) -> Booking:
        """新規予約エンティティを生成する

        Args:
            trip_id: 旅行ID（Value Object）
            flight_details: フライト詳細情報

        Returns:
            Booking: 生成された予約エンティティ（PENDING状態）
        """
        # 冪等性担保: 同じ TripId からは常に同じ BookingId を生成
        booking_id = BookingId.from_trip_id(trip_id)

        # プリミティブ型から Value Object に変換
        flight_number = FlightNumber(flight_details["flight_number"])
        departure_time = DateTime(flight_details["departure_time"])
        arrival_time = DateTime(flight_details["arrival_time"])
        price = Money(
            amount=flight_details["price_amount"],
            currency=Currency(flight_details["price_currency"]),
        )

        return Booking(
            id=booking_id,
            trip_id=trip_id,
            flight_number=flight_number,
            departure_time=departure_time,
            arrival_time=arrival_time,
            price=price,
            status=BookingStatus.PENDING,
        )
