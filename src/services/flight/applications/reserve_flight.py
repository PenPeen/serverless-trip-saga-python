from services.flight.domain.entity import Booking
from services.flight.domain.factory.booking_factory import BookingFactory, FlightDetails
from services.flight.domain.repository.booking_repository import BookingRepository
from services.shared.domain import TripId


class ReserveFlightService:
    """フライト予約サービス

    Factory と Repository を使用してエンティティの生成・永続化を行う。
    """

    def __init__(self, repository: BookingRepository, factory: BookingFactory) -> None:
        self._repository = repository
        self._factory = factory

    def reserve(self, trip_id: TripId, flight_details: FlightDetails) -> Booking:
        """フライトを予約する"""
        booking = self._factory.create(trip_id, flight_details)
        self._repository.save(booking)
        return booking
