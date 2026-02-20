from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.payment.applications.refund_payment import RefundPaymentService
from services.payment.handlers.request_models import RefundPaymentRequest
from services.payment.handlers.response_models import to_response
from services.payment.infrastructure.dynamodb_payment_repository import (
    DynamoDBPaymentRepository,
)
from services.shared.domain import TripId

logger = Logger()

repository = DynamoDBPaymentRepository()
service = RefundPaymentService(repository=repository)


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """払い戻し Lambda Handler（補償トランザクション用）"""
    logger.info("Received refund payment request")

    payload = event.get("Payload", event)
    request = RefundPaymentRequest.model_validate(payload)
    trip_id = TripId(value=request.trip_id)
    payment = service.refund(trip_id)

    if payment is None:
        return {"status": "success", "message": "Already refunded or not found"}

    return to_response(payment)
