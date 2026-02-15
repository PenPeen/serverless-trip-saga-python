from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.payment.applications.process_payment import ProcessPaymentService
from services.payment.domain.entity import Payment
from services.payment.domain.factory import PaymentFactory
from services.payment.handlers.request_models import ProcessPaymentRequest
from services.payment.handlers.response_models import (
    PaymentData,
    SuccessResponse,
)
from services.payment.infrastructure.dynamodb_payment_repository import (
    DynamoDBPaymentRepository,
)
from services.shared.domain import TripId

logger = Logger()

repository = DynamoDBPaymentRepository()
factory = PaymentFactory()
service = ProcessPaymentService(repository=repository, factory=factory)


def _to_response(payment: Payment) -> dict:
    """Entity をレスポンス形式に変換"""
    return SuccessResponse(
        data=PaymentData(
            payment_id=str(payment.id),
            trip_id=str(payment.trip_id),
            amount=str(payment.amount.amount),
            currency=str(payment.amount.currency),
            status=payment.status.value,
        )
    ).model_dump()


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """決済処理のLambdaハンドラー"""
    logger.info("Received process payment request")

    payload = event.get("Payload", event)
    request = ProcessPaymentRequest.model_validate(payload)

    trip_id = TripId(value=request.trip_id)
    payment = service.process(
        trip_id=trip_id,
        amount=request.amount,
        currency_code=request.currency,
    )
    return _to_response(payment)
