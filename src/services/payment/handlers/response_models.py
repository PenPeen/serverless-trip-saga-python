from __future__ import annotations

from pydantic import BaseModel

from services.payment.domain.entity.payment import Payment


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


def to_response(payment: Payment) -> dict:
    """Payment エンティティをレスポンス辞書に変換する"""
    return SuccessResponse(
        data=PaymentData(
            payment_id=str(payment.id),
            trip_id=str(payment.trip_id),
            amount=str(payment.amount.amount),
            currency=str(payment.amount.currency),
            status=payment.status.value,
        )
    ).model_dump()
