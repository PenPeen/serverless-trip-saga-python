from enum import Enum


class PaymentStatus(str, Enum):
    """決済ステータス"""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"
