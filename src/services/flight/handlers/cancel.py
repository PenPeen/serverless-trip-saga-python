from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.flight.applications.cancel_flight import CancelFlightService
from services.flight.handlers.request_models import CancelFlightRequest
from services.flight.handlers.response_models import to_response
from services.flight.infrastructure.dynamodb_booking_repository import (
    DynamoDBBookingRepository,
)
from services.shared.domain import TripId

logger = Logger()

repository = DynamoDBBookingRepository()
service = CancelFlightService(repository=repository)


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

    return to_response(booking)
