from services.shared.domain import TripId

from services.hotel.domain.entity import HotelBooking
from services.hotel.domain.factory import HotelBookingFactory, HotelDetails
from services.hotel.domain.repository import HotelBookingRepository


class ReserveHotelService:
    """ホテル予約ユースケース

    Hands-on 04 の ReserveFlightService と同じパターン。
    """

    def __init__(
        self,
        repository: HotelBookingRepository,
        factory: HotelBookingFactory,
    ) -> None:
        self._repository = repository
        self._factory = factory

    def reserve(self, trip_id: TripId, hotel_details: HotelDetails) -> HotelBooking:
        """ホテルを予約する

        Returns:
            HotelBooking: 予約エンティティ（Handler層でレスポンス形式に変換する）
        """
        # 1. Factory でエンティティを生成
        booking: HotelBooking = self._factory.create(trip_id, hotel_details)

        # 2. Repository で永続化
        self._repository.save(booking)

        # 3. Entity を返却
        return booking
