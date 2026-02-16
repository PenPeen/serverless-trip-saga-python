from abc import abstractmethod

from services.payment.domain.entity.payment import Payment
from services.payment.domain.value_object.payment_id import PaymentId
from services.shared.domain import Repository, TripId


class PaymentRepository(Repository[Payment, PaymentId]):
    """決済リポジトリのインターフェース"""

    @abstractmethod
    def save(self, payment: Payment) -> None:
        """決済を保存する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, payment_id: PaymentId) -> Payment | None:
        """決済IDで検索する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: TripId) -> Payment | None:
        """Trip ID で検索する"""
        raise NotImplementedError

    @abstractmethod
    def update(self, payment: Payment) -> None:
        """決済を更新する"""
        raise NotImplementedError
