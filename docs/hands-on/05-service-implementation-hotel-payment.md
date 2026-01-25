# Hands-on 05: Service Implementation - Hotel & Payment

本ハンズオンでは、Hands-on 04 で学んだ DDD パターン（Repository, Factory, Value Object）を活用し、
残りのマイクロサービス **Hotel Service** と **Payment Service** を実装します。

## 1. 目的

*   Hands-on 04 で確立したパターンを横展開し、開発効率を体感する。
*   **Repository + Factory パターン**を Hotel/Payment に適用する。
*   **共通 Value Object**（TripId, Money, Currency, IsoDateTime）を再利用する。
*   **冪等性 (Idempotency)** を実装し、二重処理を防止する。

## 2. 実装内容

| サービス | 機能 | 説明 |
|----------|------|------|
| **Hotel Service** | Reserve | ホテル予約 |
| **Hotel Service** | Cancel | ホテル予約キャンセル（補償トランザクション） |
| **Payment Service** | Process | 決済処理 |
| **Payment Service** | Refund | 払い戻し（補償トランザクション） |

## 3. 冪等性 (Idempotency) の実装

### なぜ冪等性が必要か？

*   ネットワーク再送やリトライによる「**二重決済**」「**二重予約**」を防ぐ
*   Step Functions のリトライ機能と組み合わせて堅牢なシステムを構築

### 実装方法

Lambda Powertools の Idempotency 機能を導入します。
Factory パターンで生成する ID を冪等性キーとして活用します。

```python
from aws_lambda_powertools.utilities.idempotency import (
    IdempotencyConfig,
    DynamoDBPersistenceLayer,
    idempotent_function,
)
```

## 4. Hotel Service の実装

Hands-on 04 の Flight Service と同じパターンで実装します。

### 4.1 ディレクトリ構造

Value Object と Entity はファイルを分けて配置します。

```
services/hotel/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── request_models.py        # Pydantic リクエストモデル
│   ├── reserve.py               # 予約 Lambda
│   └── cancel.py                # キャンセル Lambda（補償トランザクション）
├── applications/
│   ├── __init__.py
│   ├── reserve_hotel.py         # 予約ユースケース
│   └── cancel_hotel.py          # キャンセルユースケース
├── domain/
│   ├── __init__.py
│   ├── hotel_booking_id.py      # HotelBookingId（Value Object）
│   ├── hotel_name.py            # HotelName（Value Object）
│   ├── stay_period.py           # StayPeriod（Value Object）
│   ├── hotel_booking.py         # HotelBooking（Entity）
│   ├── hotel_booking_factory.py # Factory
│   ├── hotel_booking_repository.py  # Repository インターフェース
│   └── enum/
│       ├── __init__.py
│       └── hotel_booking_status.py  # HotelBookingStatus（Enum）
└── infrastructure/
    ├── __init__.py
    └── dynamodb_hotel_booking_repository.py  # Repository 実装
```

### 4.2 Hotel 固有の Value Object

#### HotelBookingId（`services/hotel/domain/hotel_booking_id.py`）

```python
from dataclasses import dataclass

from services.shared.domain import TripId


@dataclass(frozen=True)
class HotelBookingId:
    """ホテル予約ID（Value Object）

    不変で、値が同じなら同一とみなされる。
    """
    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_trip_id(cls, trip_id: TripId) -> "HotelBookingId":
        """TripId から冪等な HotelBookingId を生成

        同じ TripId からは常に同じ HotelBookingId が生成される。
        """
        return cls(value=f"hotel_for_{trip_id}")
```

#### HotelBookingStatus（`services/hotel/domain/enum/hotel_booking_status.py`）

```python
from enum import Enum


class HotelBookingStatus(str, Enum):
    """ホテル予約ステータス"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
```

#### HotelName（`services/hotel/domain/hotel_name.py`）

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class HotelName:
    """ホテル名（Value Object）

    ホテル名のバリデーションを行う。
    """
    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value.strip()) == 0:
            raise ValueError("Hotel name cannot be empty")
        if len(self.value) > 100:
            raise ValueError("Hotel name is too long (max 100 characters)")

    def __str__(self) -> str:
        return self.value
```

#### StayPeriod（`services/hotel/domain/stay_period.py`）

```python
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class StayPeriod:
    """滞在期間（Value Object）

    チェックイン日とチェックアウト日をまとめた Value Object。
    日付の妥当性を検証する。
    """
    check_in: str   # YYYY-MM-DD 形式
    check_out: str  # YYYY-MM-DD 形式

    def __post_init__(self) -> None:
        # 日付形式のバリデーション
        try:
            check_in_date = date.fromisoformat(self.check_in)
            check_out_date = date.fromisoformat(self.check_out)
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}") from e

        # チェックアウトはチェックインより後でなければならない
        if check_out_date <= check_in_date:
            raise ValueError("Check-out date must be after check-in date")

    def nights(self) -> int:
        """宿泊数を計算する"""
        check_in_date = date.fromisoformat(self.check_in)
        check_out_date = date.fromisoformat(self.check_out)
        return (check_out_date - check_in_date).days
```

### 4.3 Domain Layer: HotelBooking AggregateRoot

`services/hotel/domain/hotel_booking.py`

```python
from services.shared.domain import AggregateRoot, TripId, Money
from services.shared.domain.exceptions import BusinessRuleViolationException

from services.hotel.domain.hotel_booking_id import HotelBookingId
from services.hotel.domain.enum import HotelBookingStatus
from services.hotel.domain.hotel_name import HotelName
from services.hotel.domain.stay_period import StayPeriod


class HotelBooking(AggregateRoot[HotelBookingId]):
    """ホテル予約エンティティ

    AggregateRoot 基底クラスを継承し、HotelBookingId で同一性を判定する。
    全てのフィールドは Value Object で表現される。
    """

    def __init__(
        self,
        id: HotelBookingId,
        trip_id: TripId,
        hotel_name: HotelName,
        stay_period: StayPeriod,
        price: Money,
        status: HotelBookingStatus = HotelBookingStatus.PENDING,
    ) -> None:
        super().__init__(id)
        self._trip_id = trip_id
        self._hotel_name = hotel_name
        self._stay_period = stay_period
        self._price = price
        self._status = status

    @property
    def trip_id(self) -> TripId:
        return self._trip_id

    @property
    def hotel_name(self) -> HotelName:
        return self._hotel_name

    @property
    def stay_period(self) -> StayPeriod:
        return self._stay_period

    @property
    def price(self) -> Money:
        return self._price

    @property
    def status(self) -> HotelBookingStatus:
        return self._status

    def confirm(self) -> None:
        """予約を確定する"""
        if self._status == HotelBookingStatus.CANCELLED:
            raise BusinessRuleViolationException(
                "Cannot confirm a cancelled booking"
            )
        self._status = HotelBookingStatus.CONFIRMED

    def cancel(self) -> None:
        """予約をキャンセルする（補償トランザクション用）"""
        self._status = HotelBookingStatus.CANCELLED
```

> **設計ポイント:** Entity に `to_dict()` を持たせない理由は Hands-on 04 を参照。
> 永続化は Infrastructure 層、レスポンス変換は Handler 層の責務。

### 4.4 Domain Layer: hotel/domain/__init__.py

```python
from .hotel_booking_id import HotelBookingId
from .enum import HotelBookingStatus
from .hotel_name import HotelName
from .stay_period import StayPeriod
from .hotel_booking import HotelBooking

__all__ = [
    "HotelBookingId",
    "HotelBookingStatus",
    "HotelName",
    "StayPeriod",
    "HotelBooking",
]
```

### 4.5 Domain Layer: Factory

`services/hotel/domain/hotel_booking_factory.py`

```python
from decimal import Decimal
from typing import TypedDict

from services.shared.domain import TripId, Money, Currency

from services.hotel.domain.hotel_booking import HotelBooking
from services.hotel.domain.hotel_booking_id import HotelBookingId
from services.hotel.domain.enum import HotelBookingStatus
from services.hotel.domain.hotel_name import HotelName
from services.hotel.domain.stay_period import StayPeriod


class HotelDetails(TypedDict):
    """ホテル詳細の入力データ構造"""
    hotel_name: str
    check_in_date: str
    check_out_date: str
    price_amount: Decimal
    price_currency: str


class HotelBookingFactory:
    """ホテル予約ファクトリ

    - 冪等性を担保する ID 生成
    - プリミティブ型から Value Object への変換
    """

    def create(self, trip_id: TripId, hotel_details: HotelDetails) -> HotelBooking:
        """新規予約エンティティを生成する"""
        # 冪等性担保: 同じ TripId からは常に同じ HotelBookingId を生成
        booking_id = HotelBookingId.from_trip_id(trip_id)

        # プリミティブ型から Value Object に変換
        hotel_name = HotelName(hotel_details["hotel_name"])
        stay_period = StayPeriod(
            check_in=hotel_details["check_in_date"],
            check_out=hotel_details["check_out_date"],
        )
        price = Money(
            amount=hotel_details["price_amount"],
            currency=Currency(hotel_details["price_currency"]),
        )

        return HotelBooking(
            id=booking_id,
            trip_id=trip_id,
            hotel_name=hotel_name,
            stay_period=stay_period,
            price=price,
            status=HotelBookingStatus.PENDING,
        )
```

### 4.6 Domain Layer: Repository インターフェース

`services/hotel/domain/hotel_booking_repository.py`

```python
from abc import abstractmethod
from typing import Optional

from services.shared.domain import Repository, TripId

from services.hotel.domain.hotel_booking_id import HotelBookingId
from services.hotel.domain.hotel_booking import HotelBooking


class HotelBookingRepository(Repository[HotelBooking, HotelBookingId]):
    """ホテル予約リポジトリのインターフェース"""

    @abstractmethod
    def save(self, booking: HotelBooking) -> None:
        """予約を保存する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, booking_id: HotelBookingId) -> Optional[HotelBooking]:
        """予約IDで検索する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: TripId) -> Optional[HotelBooking]:
        """Trip ID で検索する"""
        raise NotImplementedError
```

### 4.7 Application Layer: 予約ユースケース

`services/hotel/applications/reserve_hotel.py`

```python
from services.shared.domain import TripId

from services.hotel.domain.hotel_booking import HotelBooking
from services.hotel.domain.hotel_booking_factory import HotelBookingFactory, HotelDetails
from services.hotel.domain.hotel_booking_repository import HotelBookingRepository


class ReserveHotelService:
    """ホテル予約ユースケース

    Hands-on 04 の ReserveFlightService と同じパターン。
    """

    def __init__(
        self,
        repository: HotelBookingRepository,
        factory: HotelBookingFactory,
    ) -> None:
        self._repository = repository
        self._factory = factory

    def reserve(self, trip_id: TripId, hotel_details: HotelDetails) -> HotelBooking:
        """ホテルを予約する

        Returns:
            HotelBooking: 予約エンティティ（Handler層でレスポンス形式に変換する）
        """
        # 1. Factory でエンティティを生成
        booking: HotelBooking = self._factory.create(trip_id, hotel_details)

        # 2. Repository で永続化
        self._repository.save(booking)

        # 3. Entity を返却
        return booking
```

### 4.8 Handler Layer: リクエストバリデーション

`services/hotel/handlers/request_models.py`

```python
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class HotelDetailsRequest(BaseModel):
    """ホテル詳細のリクエストモデル"""

    hotel_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="ホテル名",
    )
    check_in_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="チェックイン日（YYYY-MM-DD形式）",
        examples=["2024-01-01"],
    )
    check_out_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="チェックアウト日（YYYY-MM-DD形式）",
        examples=["2024-01-03"],
    )
    price_amount: Decimal = Field(
        ...,
        gt=0,
        description="料金（0より大きい値）",
    )
    price_currency: str = Field(
        default="JPY",
        pattern="^[A-Z]{3}$",
        description="通貨コード（ISO 4217）",
    )

    @field_validator("price_amount", mode="before")
    @classmethod
    def convert_price_to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class ReserveHotelRequest(BaseModel):
    """ホテル予約リクエストモデル"""

    trip_id: str = Field(..., min_length=1)
    hotel_details: HotelDetailsRequest


class CancelHotelRequest(BaseModel):
    """ホテルキャンセルリクエストモデル（補償トランザクション用）"""

    trip_id: str = Field(..., min_length=1)
```

### 4.8 Handler Layer: Lambda エントリーポイント

`services/hotel/handlers/reserve.py`

```python
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from services.shared.domain import TripId

from services.hotel.applications.reserve_hotel import ReserveHotelService
from services.hotel.infrastructure.dynamodb_hotel_booking_repository import (
    DynamoDBHotelBookingRepository,
)
from services.hotel.domain.hotel_booking_factory import HotelBookingFactory
from services.hotel.handlers.request_models import ReserveHotelRequest

logger = Logger()
tracer = Tracer()

# 依存関係の組み立て（Composition Root）
repository = DynamoDBHotelBookingRepository()
factory = HotelBookingFactory()
service = ReserveHotelService(repository=repository, factory=factory)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """ホテル予約 Lambda ハンドラ"""
    logger.info("Received reserve hotel request", extra={"event": event})

    # 入力バリデーション
    try:
        request = ReserveHotelRequest.model_validate(event)
    except ValidationError as e:
        logger.warning("Validation failed", extra={"errors": e.errors()})
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "入力データが不正です",
            "details": e.errors(),
        }

    # Application Service 呼び出し
    try:
        trip_id = TripId(value=request.trip_id)
        hotel_details = {
            "hotel_name": request.hotel_details.hotel_name,
            "check_in_date": request.hotel_details.check_in_date,
            "check_out_date": request.hotel_details.check_out_date,
            "price_amount": request.hotel_details.price_amount,
            "price_currency": request.hotel_details.price_currency,
        }
        booking = service.reserve(trip_id, hotel_details)

        # Handler層の責務: Entity をレスポンス形式に変換
        return {
            "status": "success",
            "data": {
                "booking_id": str(booking.id),
                "trip_id": str(booking.trip_id),
                "hotel_name": str(booking.hotel_name),
                "check_in_date": booking.stay_period.check_in,
                "check_out_date": booking.stay_period.check_out,
                "nights": booking.stay_period.nights(),
                "price_amount": str(booking.price.amount),
                "price_currency": str(booking.price.currency),
                "status": booking.status.value,
            },
        }

    except Exception as e:
        logger.exception("Failed to reserve hotel")
        return {"status": "error", "error_code": "INTERNAL_ERROR", "message": str(e)}
```

## 5. Payment Service の実装

決済サービスも同じパターンで実装します。

### 5.1 ディレクトリ構造

```
services/payment/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── request_models.py        # Pydantic リクエストモデル
│   ├── process.py               # 決済処理 Lambda
│   └── refund.py                # 払い戻し Lambda（補償トランザクション）
├── applications/
│   ├── __init__.py
│   ├── process_payment.py       # 決済ユースケース
│   └── refund_payment.py        # 払い戻しユースケース
├── domain/
│   ├── __init__.py
│   ├── payment_id.py            # PaymentId（Value Object）
│   ├── payment.py               # Payment（Entity）
│   ├── payment_factory.py       # Factory
│   ├── payment_repository.py    # Repository インターフェース
│   └── enum/
│       ├── __init__.py
│       └── payment_status.py    # PaymentStatus（Enum）
└── infrastructure/
    ├── __init__.py
    └── dynamodb_payment_repository.py  # Repository 実装
```

### 5.2 Payment 固有の Value Object

#### PaymentId（`services/payment/domain/payment_id.py`）

```python
from dataclasses import dataclass

from services.shared.domain import TripId


@dataclass(frozen=True)
class PaymentId:
    """決済ID（Value Object）

    不変で、値が同じなら同一とみなされる。
    """
    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_trip_id(cls, trip_id: TripId) -> "PaymentId":
        """TripId から冪等な PaymentId を生成"""
        return cls(value=f"payment_for_{trip_id}")
```

#### PaymentStatus（`services/payment/domain/enum/payment_status.py`）

```python
from enum import Enum


class PaymentStatus(str, Enum):
    """決済ステータス"""
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"
```

### 5.3 Domain Layer: Payment AggregateRoot

`services/payment/domain/payment.py`

```python
from services.shared.domain import AggregateRoot, TripId, Money
from services.shared.domain.exceptions import BusinessRuleViolationException

from services.payment.domain.payment_id import PaymentId
from services.payment.domain.enum import PaymentStatus


class Payment(AggregateRoot[PaymentId]):
    """決済エンティティ

    AggregateRoot 基底クラスを継承し、PaymentId で同一性を判定する。
    全てのフィールドは Value Object で表現される。
    """

    def __init__(
        self,
        id: PaymentId,
        trip_id: TripId,
        amount: Money,
        status: PaymentStatus = PaymentStatus.PENDING,
    ) -> None:
        super().__init__(id)
        self._trip_id = trip_id
        self._amount = amount
        self._status = status

    @property
    def trip_id(self) -> TripId:
        return self._trip_id

    @property
    def amount(self) -> Money:
        return self._amount

    @property
    def status(self) -> PaymentStatus:
        return self._status

    def complete(self) -> None:
        """決済を完了する"""
        if self._status != PaymentStatus.PENDING:
            raise BusinessRuleViolationException(
                f"Cannot complete payment in {self._status} status"
            )
        self._status = PaymentStatus.COMPLETED

    def refund(self) -> None:
        """払い戻しを行う（補償トランザクション用）"""
        if self._status != PaymentStatus.COMPLETED:
            raise BusinessRuleViolationException(
                "Can only refund completed payments"
            )
        self._status = PaymentStatus.REFUNDED
```

> **設計ポイント:** Entity に `to_dict()` を持たせない理由は Hands-on 04 を参照。

### 5.4 Domain Layer: payment/domain/__init__.py

```python
from .payment_id import PaymentId
from .enum import PaymentStatus
from .payment import Payment

__all__ = [
    "PaymentId",
    "PaymentStatus",
    "Payment",
]
```

### 5.5 Domain Layer: Factory

`services/payment/domain/payment_factory.py`

```python
from decimal import Decimal

from services.shared.domain import TripId, Money, Currency

from services.payment.domain.payment import Payment
from services.payment.domain.payment_id import PaymentId
from services.payment.domain.enum import PaymentStatus


class PaymentFactory:
    """決済ファクトリ

    - 冪等性を担保する ID 生成
    - プリミティブ型から Value Object への変換
    """

    def create(
        self,
        trip_id: TripId,
        amount: Decimal,
        currency_code: str,
    ) -> Payment:
        """新規決済エンティティを生成する"""
        # 冪等性担保: 同じ TripId からは常に同じ PaymentId を生成
        payment_id = PaymentId.from_trip_id(trip_id)

        # プリミティブ型から Value Object に変換
        money = Money(amount=amount, currency=Currency(currency_code))

        return Payment(
            id=payment_id,
            trip_id=trip_id,
            amount=money,
            status=PaymentStatus.PENDING,
        )
```

### 5.6 Application Layer: 決済ユースケース

`services/payment/applications/process_payment.py`

```python
from decimal import Decimal

from services.shared.domain import TripId

from services.payment.domain.payment import Payment
from services.payment.domain.payment_factory import PaymentFactory
from services.payment.domain.payment_repository import PaymentRepository


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
```

### 5.7 Handler Layer: リクエストバリデーション

`services/payment/handlers/request_models.py`

```python
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class ProcessPaymentRequest(BaseModel):
    """決済処理リクエストモデル"""

    trip_id: str = Field(..., min_length=1)
    amount: Decimal = Field(
        ...,
        gt=0,
        description="決済金額（0より大きい値）",
    )
    currency: str = Field(
        default="JPY",
        pattern="^[A-Z]{3}$",
        description="通貨コード（ISO 4217）",
    )

    @field_validator("amount", mode="before")
    @classmethod
    def convert_amount_to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class RefundPaymentRequest(BaseModel):
    """払い戻しリクエストモデル（補償トランザクション用）"""

    trip_id: str = Field(..., min_length=1)
```

### 5.7 Handler Layer: Lambda エントリーポイント

`services/payment/handlers/process.py`

```python
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from services.shared.domain import TripId

from services.payment.applications.process_payment import ProcessPaymentService
from services.payment.infrastructure.dynamodb_payment_repository import (
    DynamoDBPaymentRepository,
)
from services.payment.domain.payment_factory import PaymentFactory
from services.payment.handlers.request_models import ProcessPaymentRequest

logger = Logger()
tracer = Tracer()

# 依存関係の組み立て（Composition Root）
repository = DynamoDBPaymentRepository()
factory = PaymentFactory()
service = ProcessPaymentService(repository=repository, factory=factory)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """決済処理 Lambda ハンドラ"""
    logger.info("Received process payment request", extra={"event": event})

    # 入力バリデーション
    try:
        request = ProcessPaymentRequest.model_validate(event)
    except ValidationError as e:
        logger.warning("Validation failed", extra={"errors": e.errors()})
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "入力データが不正です",
            "details": e.errors(),
        }

    # Application Service 呼び出し
    try:
        trip_id = TripId(value=request.trip_id)
        payment = service.process(
            trip_id=trip_id,
            amount=request.amount,
            currency_code=request.currency,
        )

        # Handler層の責務: Entity をレスポンス形式に変換
        return {
            "status": "success",
            "data": {
                "payment_id": str(payment.id),
                "trip_id": str(payment.trip_id),
                "amount": str(payment.amount.amount),
                "currency": str(payment.amount.currency),
                "status": payment.status.value,
            },
        }

    except Exception as e:
        logger.exception("Failed to process payment")
        return {"status": "error", "error_code": "INTERNAL_ERROR", "message": str(e)}
```

## 6. CDK Construct への定義追加

Hands-on 04 で作成した `Functions` Construct に、Hotel/Payment サービスの Lambda 関数を追加します。

### infra/constructs/functions.py (追加)

```python
from aws_cdk import (
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
)
from constructs import Construct


class Functions(Construct):
    """Lambda 関数を管理する Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        table: dynamodb.Table,
        common_layer: _lambda.LayerVersion,
    ) -> None:
        super().__init__(scope, id)

        # ========================================================================
        # Flight Service Lambda (Hands-on 04 で作成済み)
        # ========================================================================
        self.flight_reserve = _lambda.Function(
            self, "FlightReserveLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.flight.handlers.reserve.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "flight-service",
            },
        )

        self.flight_cancel = _lambda.Function(
            self, "FlightCancelLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.flight.handlers.cancel.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "flight-service",
            },
        )

        # ========================================================================
        # Hotel Service Lambda (今回追加)
        # ========================================================================
        self.hotel_reserve = _lambda.Function(
            self, "HotelReserveLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.hotel.handlers.reserve.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "hotel-service",
            },
        )

        self.hotel_cancel = _lambda.Function(
            self, "HotelCancelLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.hotel.handlers.cancel.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "hotel-service",
            },
        )

        # ========================================================================
        # Payment Service Lambda (今回追加)
        # ========================================================================
        self.payment_process = _lambda.Function(
            self, "PaymentProcessLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.payment.handlers.process.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "payment-service",
            },
        )

        self.payment_refund = _lambda.Function(
            self, "PaymentRefundLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.payment.handlers.refund.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "payment-service",
            },
        )

        # ========================================================================
        # DynamoDB への読み書き権限を付与
        # ========================================================================
        table.grant_read_write_data(self.flight_reserve)
        table.grant_read_write_data(self.flight_cancel)
        table.grant_read_write_data(self.hotel_reserve)
        table.grant_read_write_data(self.hotel_cancel)
        table.grant_read_write_data(self.payment_process)
        table.grant_read_write_data(self.payment_refund)
```

## 7. 単体テストの配置

### テストファイル構造

```
tests/unit/services/
├── shared/
│   └── domain/
│       ├── test_trip_id.py
│       ├── test_money.py
│       ├── test_currency.py
│       └── test_date_time.py
├── hotel/
│   ├── domain/
│   │   ├── test_hotel_booking_id.py
│   │   ├── test_hotel_name.py
│   │   ├── test_stay_period.py
│   │   └── test_hotel_booking.py
│   ├── test_hotel_booking_factory.py
│   └── test_reserve_hotel.py
└── payment/
    ├── domain/
    │   ├── test_payment_id.py
    │   └── test_payment.py
    ├── test_payment_factory.py
    └── test_process_payment.py
```

## 8. パターンの効果

Hands-on 04 で確立したパターンにより、以下の効果が得られます：

| 効果 | 説明 |
|------|------|
| **開発効率** | 同じ構造を横展開するだけで新サービスを追加可能 |
| **テスト容易性** | Repository をモックに差し替えて単体テスト可能 |
| **保守性** | 責務が明確に分離され、変更の影響範囲が限定的 |
| **冪等性** | Factory での ID 生成により、リトライ時も同じエンティティを生成 |
| **型安全性** | Value Object により、プリミティブ型の取り違えを防止 |
| **ドメイン表現** | Value Object によりビジネスルールがコードで表現される |

## 9. 次のステップ

3つのマイクロサービス（Flight, Hotel, Payment）の実装が完了しました。
次は、これらを Step Functions で連携させ、Saga パターンを実現します。

👉 **[Hands-on 06: Step Functions Orchestration](./06-step-functions-orchestration.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/hotel-payment-service`
*   **コミットメッセージ**: `HotelおよびPaymentサービスの実装`
