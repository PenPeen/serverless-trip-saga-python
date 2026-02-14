from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.hotel.applications.reserve_hotel import ReserveHotelService
from services.hotel.domain.entity import HotelBooking
from services.hotel.domain.factory import HotelBookingFactory
from services.hotel.domain.factory.hotel_booking_factory import HotelDetails
from services.hotel.handlers.request_models import ReserveHotelRequest
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
factory = HotelBookingFactory()
service = ReserveHotelService(repository=repository, factory=factory)


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
@event_parser(model=ReserveHotelRequest)
def lambda_handler(event: ReserveHotelRequest, context: LambdaContext) -> dict:
    """ホテル予約 Lambda ハンドラ"""
    logger.info("Received reserve hotel request")

    trip_id = TripId(value=event.trip_id)
    hotel_details: HotelDetails = {
        "hotel_name": event.hotel_details.hotel_name,
        "check_in_date": event.hotel_details.check_in_date,
        "check_out_date": event.hotel_details.check_out_date,
        "price_amount": event.hotel_details.price_amount,
        "price_currency": event.hotel_details.price_currency,
    }
    booking = service.reserve(trip_id, hotel_details)
    return _to_response(booking)
