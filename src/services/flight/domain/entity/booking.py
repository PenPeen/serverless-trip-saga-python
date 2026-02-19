from services.flight.domain.enum import BookingStatus
from services.flight.domain.value_object import BookingId, FlightNumber
from services.shared.domain import AggregateRoot, IsoDateTime, Money, TripId
from services.shared.domain.exception import BusinessRuleViolationException


class Booking(AggregateRoot[BookingId]):
    """フライト予約"""

    def __init__(
        self,
        id: BookingId,
        trip_id: TripId,
        flight_number: FlightNumber,
        departure_time: IsoDateTime,
        arrival_time: IsoDateTime,
        price: Money,
        status: BookingStatus = BookingStatus.PENDING,
    ) -> None:
        super().__init__(id)

        self._trip_id = trip_id
        self._flight_number = flight_number
        self._departure_time = departure_time
        self._arrival_time = arrival_time
        self._price = price
        self._status = status

        self._validate_schedule()

    def _validate_schedule(self) -> None:
        """出発時刻 < 到着時刻"""
        if not self._departure_time.is_before(self._arrival_time):
            raise BusinessRuleViolationException(
                "Departure time must be before arrival time"
            )

    @property
    def trip_id(self) -> TripId:
        return self._trip_id

    @property
    def flight_number(self) -> FlightNumber:
        return self._flight_number

    @property
    def departure_time(self) -> IsoDateTime:
        return self._departure_time

    @property
    def arrival_time(self) -> IsoDateTime:
        return self._arrival_time

    @property
    def price(self) -> Money:
        return self._price

    @property
    def status(self) -> BookingStatus:
        return self._status

    def confirm(self) -> None:
        """予約を確定する"""
        if self._status == BookingStatus.CANCELLED:
            raise BusinessRuleViolationException("Cannot confirm a cancelled booking")

        self._status = BookingStatus.CONFIRMED

    def cancel(self) -> None:
        """予約をキャンセルする"""
        if self._status == BookingStatus.CANCELLED:
            return
        self._status = BookingStatus.CANCELLED
