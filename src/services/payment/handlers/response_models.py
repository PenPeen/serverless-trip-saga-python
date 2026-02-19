from pydantic import BaseModel


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
