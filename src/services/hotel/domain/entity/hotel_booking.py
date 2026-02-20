from services.hotel.domain.enum import HotelBookingStatus
from services.hotel.domain.value_object import HotelBookingId, HotelName, StayPeriod
from services.shared.domain import AggregateRoot, Money, TripId
from services.shared.domain.exception import BusinessRuleViolationException


class HotelBooking(AggregateRoot[HotelBookingId]):
    """ホテル予約エンティティ"""

    def __init__(
        self,
        id: HotelBookingId,
        trip_id: TripId,
        hotel_name: HotelName,
        stay_period: StayPeriod,
        price: Money,
        status: HotelBookingStatus = HotelBookingStatus.PENDING,
    ) -> None:
        super().__init__(id)
        self._trip_id = trip_id
        self._hotel_name = hotel_name
        self._stay_period = stay_period
        self._price = price
        self._status = status

    @property
    def trip_id(self) -> TripId:
        return self._trip_id

    @property
    def hotel_name(self) -> HotelName:
        return self._hotel_name

    @property
    def stay_period(self) -> StayPeriod:
        return self._stay_period

    @property
    def price(self) -> Money:
        return self._price

    @property
    def status(self) -> HotelBookingStatus:
        return self._status

    def confirm(self) -> None:
        """予約を確定する"""
        if self.status == HotelBookingStatus.CANCELED:
            raise BusinessRuleViolationException("Cannot confirm a cancelled booking")
        self._status = HotelBookingStatus.CONFIRMED

    def cancel(self) -> None:
        """予約をキャンセルする"""
        if self._status == HotelBookingStatus.CANCELED:
            return
        self._status = HotelBookingStatus.CANCELED
