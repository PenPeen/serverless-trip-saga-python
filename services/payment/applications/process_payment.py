from decimal import Decimal

from services.shared.domain import TripId

from services.payment.domain.entity import Payment
from services.payment.domain.factory import PaymentFactory
from services.payment.domain.repository import PaymentRepository


class ProcessPaymentService:
    """決済処理ユースケース

    Hands-on 04 の ReserveFlightService と同じパターン。
    """

    def __init__(
        self,
        repository: PaymentRepository,
        factory: PaymentFactory,
    ) -> None:
        self._repository = repository
        self._factory = factory

    def process(
        self,
        trip_id: TripId,
        amount: Decimal,
        currency_code: str,
    ) -> Payment:
        """決済を処理する

        Returns:
            Payment: 決済エンティティ（Handler層でレスポンス形式に変換する）
        """
        # 1. Factory でエンティティを生成
        payment: Payment = self._factory.create(trip_id, amount, currency_code)

        # 2. 決済を完了
        payment.complete()

        # 3. Repository で永続化
        self._repository.save(payment)

        # 4. Entity を返却
        return payment
