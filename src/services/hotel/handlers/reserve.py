from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.hotel.applications.reserve_hotel import ReserveHotelService
from services.hotel.domain.factory import HotelBookingFactory
from services.hotel.domain.factory.hotel_booking_factory import HotelDetails
from services.hotel.handlers.request_models import ReserveHotelRequest
from services.hotel.handlers.response_models import to_response
from services.hotel.infrastructure.dynamodb_hotel_booking_repository import (
    DynamoDBHotelBookingRepository,
)
from services.shared.domain import TripId

logger = Logger()


repository = DynamoDBHotelBookingRepository()
factory = HotelBookingFactory()
service = ReserveHotelService(repository=repository, factory=factory)


def _to_hotel_details(request: ReserveHotelRequest) -> HotelDetails:
    """リクエストボディから HotelDetails を構築する"""
    return {
        "hotel_name": request.hotel_details.hotel_name,
        "check_in_date": request.hotel_details.check_in_date,
        "check_out_date": request.hotel_details.check_out_date,
        "price_amount": request.hotel_details.price_amount,
        "price_currency": request.hotel_details.price_currency,
    }


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """ホテル予約 Lambda ハンドラ"""
    logger.info("Received reserve hotel request")

    payload = event.get("Payload", event)
    request = ReserveHotelRequest.model_validate(payload)

    trip_id = TripId(value=request.trip_id)
    hotel_details = _to_hotel_details(request)
    booking = service.reserve(trip_id, hotel_details)
    return to_response(booking)
