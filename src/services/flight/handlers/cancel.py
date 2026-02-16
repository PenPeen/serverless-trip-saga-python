from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.flight.applications.cancel_flight import CancelFlightService
from services.flight.domain.entity.booking import Booking
from services.flight.handlers.request_models import CancelFlightRequest
from services.flight.handlers.response_models import (
    BookingData,
    SuccessResponse,
)
from services.flight.infrastructure.dynamodb_booking_repository import (
    DynamoDBBookingRepository,
)
from services.shared.domain import TripId

logger = Logger()

repository = DynamoDBBookingRepository()
service = CancelFlightService(repository=repository)


def _to_response(booking: Booking) -> dict:
    """Entity をレスポンス形式に変換"""
    return SuccessResponse(
        data=BookingData(
            booking_id=str(booking.id),
            trip_id=str(booking.trip_id),
            flight_number=str(booking.flight_number),
            departure_time=str(booking.departure_time),
            arrival_time=str(booking.arrival_time),
            price_amount=str(booking.price.amount),
            price_currency=str(booking.price.currency),
            status=booking.status.value,
        )
    ).model_dump()


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """フライト予約キャンセル Lambda Handler（補償トランザクション用）"""
    logger.info("Received cancel flight request")

    payload = event.get("Payload", event)
    request = CancelFlightRequest.model_validate(payload)
    trip_id = TripId(value=request.trip_id)
    booking = service.cancel(trip_id)

    if booking is None:
        return {"status": "success", "message": "Already cancelled or not found"}

    return _to_response(booking)
