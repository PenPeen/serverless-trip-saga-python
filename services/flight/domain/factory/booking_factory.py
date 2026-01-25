from decimal import Decimal
from typing import TypedDict

from services.flight.domain.entity import Booking
from services.flight.domain.value_object import BookingId, FlightNumber
from services.shared.domain import IsoDateTime, Money, TripId
from services.shared.domain.value_object.currency import Currency


class FlightDetails(TypedDict):
    """フライトの入力データ構造（TypeDict）"""

    flight_number: str
    departure_time: str
    arrival_time: str
    price_amount: Decimal
    price_currency: str


class BookingFactory:
    """フライト予約Entityを生成するFactory"""

    def create(self, trip_id: TripId, flight_details: FlightDetails) -> Booking:
        """新規予約Entityを作成する"""

        booking_id = BookingId.from_trip_id(trip_id)

        flight_number = FlightNumber(flight_details["flight_number"])
        departure_time = IsoDateTime.from_string(flight_details["departure_time"])
        arrival_time = IsoDateTime.from_string(flight_details["arrival_time"])
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
        )
