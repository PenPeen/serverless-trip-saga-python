from decimal import Decimal
from typing import TypedDict

from services.hotel.domain.entity.hotel_booking import HotelBooking
from services.hotel.domain.enum.hotel_booking_status import HotelBookingStatus
from services.hotel.domain.value_object.hotel_name import HotelName
from services.hotel.domain.value_object.stay_period import StayPeriod
from services.shared.domain.value_object.currency import Currency
from services.shared.domain.value_object.money import Money
from services.shared.domain.value_object.trip_id import TripId


class HotelDetails(TypedDict):
    """ホテル詳細の入力データ"""

    hotel_name: str
    check_in_date: str
    check_out_date: str
    price_amount: Decimal
    price_currency: str


class HotelBookingFactory:
    """ホテル予約情報を生成するFactory"""

    def create(self, trip_id: TripId, hotel_details: HotelDetails) -> HotelBooking
        """新規予約のエンティティを作成する"""

        booking_id = HotelBooking.from_trip_id(trip_id)

        hotel_name = HotelName(hotel_details["hotel_name"])
        stay_period = StayPeriod(
            check_in=hotel_details["check_in_date"],
            check_out=hotel_details["check_out_date"],
        )
        price = Money(amount=hotel_details["price_amount"])
        currency = Currency(hotel_details["price_currency"])

        return HotelBooking(
            id=booking_id,
            trip_id=trip_id,
            hotel_name=hotel_name,
            stay_period=stay_period,
            price=price,
            status=HotelBookingStatus.PENDING,
        )
