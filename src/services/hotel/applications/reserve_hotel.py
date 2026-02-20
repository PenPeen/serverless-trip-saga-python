from services.hotel.domain.entity import HotelBooking
from services.hotel.domain.factory import HotelBookingFactory, HotelDetails
from services.hotel.domain.repository import HotelBookingRepository
from services.shared.domain import TripId


class ReserveHotelService:
    """ホテル予約のユースケース"""

    def __init__(
        self, repository: HotelBookingRepository, factory: HotelBookingFactory
    ) -> None:
        self._repository = repository
        self._factory = factory

    def reserve(self, trip_id: TripId, hotel_details: HotelDetails) -> HotelBooking:
        """ホテルを予約する"""

        booking: HotelBooking = self._factory.create(trip_id, hotel_details)
        self._repository.save(booking)
        return booking
