from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.domain.factory import BookingFactory
from services.flight.domain.factory.booking_factory import FlightDetails
from services.flight.handlers.request_models import ReserveFlightRequest
from services.flight.handlers.response_models import to_response
from services.flight.infrastructure.dynamodb_booking_repository import (
    DynamoDBBookingRepository,
)
from services.shared.domain import TripId

logger = Logger()


repository = DynamoDBBookingRepository()
factory = BookingFactory()
service = ReserveFlightService(repository=repository, factory=factory)


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """フライト予約 Lambda Handler

    Step Functions からの入力を受け取り、フライト予約処理を実行する。
    payload にはDatadog トレースマージ用のコンテキストが含まれるため、
    Payload キーからビジネスデータを取り出してバリデーションする。
    """

    logger.info("Received reserve flight request")

    payload = event.get("Payload", event)
    request = ReserveFlightRequest.model_validate(payload)

    trip_id = TripId(value=request.trip_id)
    flight_details = _to_flight_details(request)
    booking = service.reserve(trip_id, flight_details)
    return to_response(booking)


def _to_flight_details(request: ReserveFlightRequest) -> FlightDetails:
    """リクエストボディから FlightDetails を構築する"""

    return {
        "flight_number": request.flight_details.flight_number,
        "departure_time": request.flight_details.departure_time,
        "arrival_time": request.flight_details.arrival_time,
        "price_amount": request.flight_details.price_amount,
        "price_currency": request.flight_details.price_currency,
    }
