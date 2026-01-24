from services.flight.domain.value_object import BookingId, BookingStatus, FlightNumber
from services.shared.domain import DateTime, Entity, Money, TripId
from services.shared.domain.exception import BusinessRuleViolationException


class Booking(Entity[BookingId]):
    """フライト予約エンティティ

    Entity 基底クラスを継承し、BookingId で同一性を判定する。
    全てのフィールドは Value Object で表現される。
    """

    def __init__(
        self,
        id: BookingId,
        trip_id: TripId,
        flight_number: FlightNumber,
        departure_time: DateTime,
        arrival_time: DateTime,
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

        # ドメイン不変条件の検証
        self._validate_schedule()

    def _validate_schedule(self) -> None:
        """出発時刻は到着時刻より前でなければならない"""
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
    def departure_time(self) -> DateTime:
        return self._departure_time

    @property
    def arrival_time(self) -> DateTime:
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
        """予約をキャンセルする（補償トランザクション用）"""
        self._status = BookingStatus.CANCELLED

    def to_dict(self) -> dict:
        """永続化用の辞書表現を返す"""
        return {
            "booking_id": str(self.id),
            "trip_id": str(self._trip_id),
            "flight_number": str(self._flight_number),
            "departure_time": str(self._departure_time),
            "arrival_time": str(self._arrival_time),
            "price_amount": str(self._price.amount),
            "price_currency": str(self._price.currency),
            "status": self._status.value,
        }
