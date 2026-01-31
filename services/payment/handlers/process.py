from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel

from services.shared.domain import TripId

from services.payment.applications.process_payment import ProcessPaymentService
from services.payment.domain.entity import Payment
from services.payment.infrastructure.dynamodb_payment_repository import (
    DynamoDBPaymentRepository,
)
from services.payment.domain.factory import PaymentFactory
from services.payment.handlers.request_models import ProcessPaymentRequest

logger = Logger()


# =============================================================================
# レスポンスモデル（Pydantic）
# =============================================================================
class PaymentData(BaseModel):
    """決済データのレスポンスモデル"""

    payment_id: str
    trip_id: str
    amount: str
    currency: str
    status: str


class SuccessResponse(BaseModel):
    """成功レスポンスモデル"""

    status: str = "success"
    data: PaymentData


class ErrorResponse(BaseModel):
    """エラーレスポンスモデル"""

    status: str = "error"
    error_code: str
    message: str
    details: list | None = None


# =============================================================================
# 依存関係の組み立て（Composition Root）
# =============================================================================
repository = DynamoDBPaymentRepository()
factory = PaymentFactory()
service = ProcessPaymentService(repository=repository, factory=factory)


# =============================================================================
# ヘルパー関数
# =============================================================================
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


def _error_response(
    error_code: str, message: str, details: list | None = None
) -> dict:
    """エラーレスポンスを生成"""
    return ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
    ).model_dump(exclude_none=True)


# =============================================================================
# Lambda エントリーポイント
# =============================================================================
@logger.inject_lambda_context
@event_parser(model=ProcessPaymentRequest)
def lambda_handler(event: ProcessPaymentRequest, context: LambdaContext) -> dict:
    """決済処理 Lambda ハンドラ

    @event_parser デコレータで自動バリデーション後、決済処理を実行する。
    バリデーションエラーは ValidationError として raise され、Step Functions でハンドリング可能。
    """
    logger.info("Received process payment request")

    try:
        trip_id = TripId(value=event.trip_id)
        payment = service.process(
            trip_id=trip_id,
            amount=event.amount,
            currency_code=event.currency,
        )
        return _to_response(payment)

    except Exception as e:
        logger.exception("Failed to process payment")
        return _error_response("INTERNAL_ERROR", str(e))
