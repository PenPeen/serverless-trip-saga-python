from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.hotel.applications.cancel_hotel import CancelHotelService
from services.hotel.domain.entity import HotelBooking
from services.hotel.handlers.request_models import CancelHotelRequest
from services.hotel.handlers.response_models import (
    HotelBookingData,
    SuccessResponse,
)
from services.hotel.infrastructure.dynamodb_hotel_booking_repository import (
    DynamoDBHotelBookingRepository,
)
from services.shared.domain import TripId

logger = Logger()

repository = DynamoDBHotelBookingRepository()
service = CancelHotelService(repository=repository)


def _to_response(booking: HotelBooking) -> dict:
    """Entity をレスポンス形式に変換"""
    return SuccessResponse(
        data=HotelBookingData(
            booking_id=str(booking.id),
            trip_id=str(booking.trip_id),
            hotel_name=str(booking.hotel_name),
            check_in_date=booking.stay_period.check_in,
            check_out_date=booking.stay_period.check_out,
            nights=booking.stay_period.nights(),
            price_amount=str(booking.price.amount),
            price_currency=str(booking.price.currency),
            status=booking.status.value,
        )
    ).model_dump()


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """ホテル予約キャンセル Lambda Handler（補償トランザクション用）"""
    logger.info("Received cancel hotel request")

    payload = event.get("Payload", event)
    request = CancelHotelRequest.model_validate(payload)
    trip_id = TripId(value=request.trip_id)
    booking = service.cancel(trip_id)

    if booking is None:
        return {"status": "success", "message": "Already cancelled or not found"}

    return _to_response(booking)
