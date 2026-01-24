# Hands-on 05: Service Implementation - Hotel & Payment

本ハンズオンでは、Hands-on 04 で学んだ DDD パターン（Repository, Factory）を活用し、
残りのマイクロサービス **Hotel Service** と **Payment Service** を実装します。

## 1. 目的

*   Hands-on 04 で確立したパターンを横展開し、開発効率を体感する。
*   **Repository + Factory パターン**を Hotel/Payment に適用する。
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

```
services/hotel/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── reserve.py           # 予約 Lambda
│   └── cancel.py            # キャンセル Lambda（補償トランザクション）
├── applications/
│   ├── __init__.py
│   ├── reserve_hotel.py     # 予約ユースケース
│   └── cancel_hotel.py      # キャンセルユースケース
├── domain/
│   ├── __init__.py
│   ├── hotel_booking.py         # Entity & ValueObject
│   ├── hotel_booking_factory.py # Factory
│   └── hotel_booking_repository.py  # Repository インターフェース
└── adapters/
    ├── __init__.py
    └── dynamodb_hotel_booking_repository.py  # Repository 実装
```

### 4.2 Domain Layer: Entity (`services/hotel/domain/hotel_booking.py`)

```python
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
from datetime import date

from services.shared.domain import Entity
from services.shared.domain.exceptions import BusinessRuleViolationException


class HotelBookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class HotelBookingId:
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass
class HotelBooking(Entity[HotelBookingId]):
    """ホテル予約エンティティ"""

    trip_id: str
    hotel_name: str
    check_in_date: str
    check_out_date: str
    price: Decimal
    status: HotelBookingStatus = field(default=HotelBookingStatus.PENDING)

    @property
    def id(self) -> HotelBookingId:
        return self._id

    def confirm(self) -> None:
        if self.status == HotelBookingStatus.CANCELLED:
            raise BusinessRuleViolationException(
                "Cannot confirm a cancelled booking"
            )
        self.status = HotelBookingStatus.CONFIRMED

    def cancel(self) -> None:
        """予約をキャンセルする（補償トランザクション用）"""
        self.status = HotelBookingStatus.CANCELLED

    def to_dict(self) -> dict:
        return {
            "booking_id": str(self._id),
            "trip_id": self.trip_id,
            "hotel_name": self.hotel_name,
            "check_in_date": self.check_in_date,
            "check_out_date": self.check_out_date,
            "price": str(self.price),
            "status": self.status.value,
        }
```

### 4.3 Domain Layer: Factory (`services/hotel/domain/hotel_booking_factory.py`)

```python
from decimal import Decimal
from typing import TypedDict

from services.shared.domain import Factory
from services.hotel.domain.hotel_booking import (
    HotelBooking,
    HotelBookingId,
    HotelBookingStatus,
)


class HotelDetails(TypedDict):
    hotel_name: str
    check_in_date: str
    check_out_date: str
    price: Decimal


class HotelBookingFactory(Factory[HotelBooking]):
    """ホテル予約ファクトリ"""

    def create(self, trip_id: str, hotel_details: HotelDetails) -> HotelBooking:
        # 冪等性担保: 同じ trip_id からは常に同じ booking_id を生成
        booking_id = HotelBookingId(value=f"hotel_for_{trip_id}")

        return HotelBooking(
            _id=booking_id,
            trip_id=trip_id,
            hotel_name=hotel_details["hotel_name"],
            check_in_date=hotel_details["check_in_date"],
            check_out_date=hotel_details["check_out_date"],
            price=hotel_details["price"],
            status=HotelBookingStatus.PENDING,
        )
```

### 4.4 Domain Layer: Repository インターフェース

```python
from abc import abstractmethod
from typing import Optional

from services.shared.domain import Repository
from services.hotel.domain.hotel_booking import HotelBooking, HotelBookingId


class HotelBookingRepository(Repository[HotelBooking, HotelBookingId]):
    """ホテル予約リポジトリのインターフェース"""

    @abstractmethod
    def save(self, booking: HotelBooking) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, booking_id: HotelBookingId) -> Optional[HotelBooking]:
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: str) -> Optional[HotelBooking]:
        raise NotImplementedError
```

## 5. Payment Service の実装

決済サービスも同じパターンで実装します。

### 5.1 ディレクトリ構造

```
services/payment/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── process.py           # 決済処理 Lambda
│   └── refund.py            # 払い戻し Lambda（補償トランザクション）
├── applications/
│   ├── __init__.py
│   ├── process_payment.py   # 決済ユースケース
│   └── refund_payment.py    # 払い戻しユースケース
├── domain/
│   ├── __init__.py
│   ├── payment.py               # Entity & ValueObject
│   ├── payment_factory.py       # Factory
│   └── payment_repository.py    # Repository インターフェース
└── adapters/
    ├── __init__.py
    └── dynamodb_payment_repository.py  # Repository 実装
```

### 5.2 Domain Layer: Entity (`services/payment/domain/payment.py`)

```python
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

from services.shared.domain import Entity
from services.shared.domain.exceptions import BusinessRuleViolationException


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class PaymentId:
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass
class Payment(Entity[PaymentId]):
    """決済エンティティ"""

    trip_id: str
    amount: Decimal
    currency: str
    status: PaymentStatus = field(default=PaymentStatus.PENDING)

    @property
    def id(self) -> PaymentId:
        return self._id

    def complete(self) -> None:
        """決済を完了する"""
        if self.status != PaymentStatus.PENDING:
            raise BusinessRuleViolationException(
                f"Cannot complete payment in {self.status} status"
            )
        self.status = PaymentStatus.COMPLETED

    def refund(self) -> None:
        """払い戻しを行う（補償トランザクション用）"""
        if self.status != PaymentStatus.COMPLETED:
            raise BusinessRuleViolationException(
                "Can only refund completed payments"
            )
        self.status = PaymentStatus.REFUNDED

    def to_dict(self) -> dict:
        return {
            "payment_id": str(self._id),
            "trip_id": self.trip_id,
            "amount": str(self.amount),
            "currency": self.currency,
            "status": self.status.value,
        }
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

## 7. パターンの効果

Hands-on 04 で確立したパターンにより、以下の効果が得られます：

| 効果 | 説明 |
|------|------|
| **開発効率** | 同じ構造を横展開するだけで新サービスを追加可能 |
| **テスト容易性** | Repository をモックに差し替えて単体テスト可能 |
| **保守性** | 責務が明確に分離され、変更の影響範囲が限定的 |
| **冪等性** | Factory でのID生成により、リトライ時も同じエンティティを生成 |

## 8. 次のステップ

3つのマイクロサービス（Flight, Hotel, Payment）の実装が完了しました。
次は、これらを Step Functions で連携させ、Saga パターンを実現します。

👉 **[Hands-on 06: Step Functions Orchestration](./06-step-functions-orchestration.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/hotel-payment-service`
*   **コミットメッセージ**: `HotelおよびPaymentサービスの実装`
