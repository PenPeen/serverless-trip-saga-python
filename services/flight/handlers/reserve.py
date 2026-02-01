from typing import Optional

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel

from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.domain.entity.booking import Booking
from services.flight.domain.factory import BookingFactory
from services.flight.domain.factory.booking_factory import FlightDetails
from services.flight.handlers.request_models import ReserveFlightRequest
from services.flight.infrastructure.dynamodb_booking_repository import (
    DynamoDBBookingRepository,
)
from services.shared.domain import TripId

logger = Logger()


class BookingData(BaseModel):
    """予約データのレスポンスモデル"""

    booking_id: str
    trip_id: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price_amount: str
    price_currency: str
    status: str


class SuccessResponse(BaseModel):
    """成功レスポンスモデル"""

    status: str = "success"
    data: BookingData


class ErrorResponse(BaseModel):
    """エラーレスポンスモデル"""

    status: str = "error"
    error_code: str
    message: str
    details: list | None = None


repository = DynamoDBBookingRepository()
factory = BookingFactory()
service = ReserveFlightService(repository=repository, factory=factory)


@logger.inject_lambda_context
@event_parser(model=ReserveFlightRequest)
def lambda_handler(event: ReserveFlightRequest, context: LambdaContext) -> dict:
    """フライト予約 Lambda Handler

    Step Functions からの入力を受け取り、
    @event_parser デコレータで自動バリデーション後、フライト予約処理を実行する。
    バリデーションエラーは ValidationError として raise され、
    Step Functions でハンドリング可能。
    """

    logger.info("Received reserve flight request")

    try:
        trip_id = TripId(value=event.trip_id)
        flight_details = _to_flight_details(event)
        booking = service.reserve(trip_id, flight_details)
        return _to_response(booking)
    except Exception as e:
        logger.exception("Failed to reserve flight")
        return _error_response("INTERNAL_ERROR", str(e))


def _to_flight_details(request: ReserveFlightRequest) -> FlightDetails:
    """リクエストボディから FlightDetails を構築する"""

    return {
        "flight_number": request.flight_details.flight_number,
        "departure_time": request.flight_details.departure_time,
        "arrival_time": request.flight_details.arrival_time,
        "price_amount": request.flight_details.price_amount,
        "price_currency": request.flight_details.price_currency,
    }


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


def _error_response(
    error_code: str, message: str, details: Optional[list] = None
) -> dict:
    """エラーレスポンスを生成"""
    return ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
    ).model_dump(exclude_none=True)
