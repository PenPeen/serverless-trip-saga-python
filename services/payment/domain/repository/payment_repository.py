from abc import abstractmethod
from typing import Optional

from services.shared.domain import Repository, TripId

from services.payment.domain.value_object.payment_id import PaymentId
from services.payment.domain.entity.payment import Payment


class PaymentRepository(Repository[Payment, PaymentId]):
    """決済リポジトリのインターフェース"""

    @abstractmethod
    def save(self, payment: Payment) -> None:
        """決済を保存する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, payment_id: PaymentId) -> Optional[Payment]:
        """決済IDで検索する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: TripId) -> Optional[Payment]:
        """Trip ID で検索する"""
        raise NotImplementedError
