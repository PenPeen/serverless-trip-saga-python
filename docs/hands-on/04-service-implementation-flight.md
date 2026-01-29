# Hands-on 04: Service Implementation - Flight

本ハンズオンでは、最初のマイクロサービスである **Flight Service** (フライト予約) を実装します。
DDD (ドメイン駆動設計) のレイヤー構造を適用し、Hands-on 03 で作成した DDD Building Blocks を活用します。

## 1. 目的
*   DDD レイヤー (Handler, Application, Domain, Infrastructure) に基づいた Lambda 実装を行う。
*   **Repository パターン** を適用し、永続化を抽象化する。
*   **Factory パターン** を適用し、エンティティ生成ロジックを分離する。
*   **Value Object** を適切に設計し、ドメインの概念を型で表現する。
*   `pytest` を用いた単体テストを作成し、ロジックの正当性を検証する。
*   DynamoDB へのデータ書き込みを実装する。

## 2. ディレクトリ構造

### 2.1 共通 Value Object（shared/domain/）

複数のサービスで共通して使用する Value Object を `shared/domain/` に配置します。
種別ごとにサブディレクトリを分けて整理します。

```
services/shared/domain/
├── __init__.py                    # 全体の re-export
├── entity/
│   ├── __init__.py
│   ├── entity.py                 # Entity 基底クラス（Hands-on 03 で作成済み）
│   └── aggregate.py              # AggregateRoot 基底クラス（Hands-on 03 で作成済み）
├── value_object/
│   ├── __init__.py
│   ├── trip_id.py                # TripId（全サービス共通）
│   ├── currency.py               # Currency（通貨）
│   ├── money.py                  # Money（金額）
│   └── iso_date_time.py              # IsoDateTime（日時）
├── repository/
│   ├── __init__.py
│   └── repository.py             # Repository 基底クラス（Hands-on 03 で作成済み）
└── exception/
    ├── __init__.py
    └── exceptions.py             # 例外（Hands-on 03 で作成済み）
```

### 2.2 Flight Service（flight/）

Value Object と Entity は種別ごとにサブディレクトリを分けて配置します。

```
services/flight/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── request_models.py      # Pydantic リクエストモデル（バリデーション）
│   └── reserve.py             # Lambda エントリーポイント
├── applications/
│   ├── __init__.py
│   └── reserve_flight.py      # ユースケース
├── domain/
│   ├── __init__.py
│   ├── entity/
│   │   ├── __init__.py
│   │   └── booking.py         # Booking（Entity）
│   ├── value_object/
│   │   ├── __init__.py
│   │   ├── booking_id.py      # BookingId（Value Object）
│   │   └── flight_number.py   # FlightNumber（Value Object）
│   ├── enum/
│   │   ├── __init__.py
│   │   └── booking_status.py  # BookingStatus（Enum）
│   ├── repository/
│   │   ├── __init__.py
│   │   └── booking_repository.py  # Repository インターフェース
│   └── factory/
│       ├── __init__.py
│       └── booking_factory.py # Factory
└── infrastructure/
    ├── __init__.py
    └── dynamodb_booking_repository.py  # Repository 具象実装
```

## 3. 実装ステップ

### 3.1 共通 Value Object の実装

まず、複数サービスで共通して使用する Value Object を実装します。

#### TripId（`services/shared/domain/value_object/trip_id.py`）

全サービスで使用される旅行IDです。

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TripId:
    """旅行ID（全サービス共通）

    Value Object として不変性を保証。
    同じ値を持つ TripId は同一とみなされる。
    """
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("TripId cannot be empty")

    def __str__(self) -> str:
        return self.value
```

#### Currency（`services/shared/domain/value_object/currency.py`）

ISO 4217 に準拠した通貨コードを表現します。

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Currency:
    """通貨コード（ISO 4217）

    例: JPY, USD, EUR
    """
    code: str

    def __post_init__(self) -> None:
        if len(self.code) != 3 or not self.code.isalpha():
            raise ValueError(f"Invalid currency code: {self.code}")
        # frozen=True でも __post_init__ 内では object.__setattr__ が必要
        object.__setattr__(self, "code", self.code.upper())

    def __str__(self) -> str:
        return self.code

    @classmethod
    def jpy(cls) -> "Currency":
        """日本円"""
        return cls("JPY")

    @classmethod
    def usd(cls) -> "Currency":
        """米ドル"""
        return cls("USD")
```

#### Money（`services/shared/domain/value_object/money.py`）

金額と通貨を組み合わせた Value Object です。

```python
from dataclasses import dataclass
from decimal import Decimal

from .currency import Currency


@dataclass(frozen=True)
class Money:
    """金額（通貨情報を含む）

    Value Object として不変性を保証。
    金額の演算メソッドを提供。
    """
    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"

    def add(self, other: "Money") -> "Money":
        """金額を加算する"""
        if self.currency != other.currency:
            raise ValueError("Cannot add money with different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    @classmethod
    def jpy(cls, amount: Decimal | int | str) -> "Money":
        """日本円で Money を生成"""
        return cls(amount=Decimal(str(amount)), currency=Currency.jpy())

    @classmethod
    def usd(cls, amount: Decimal | int | str) -> "Money":
        """米ドルで Money を生成"""
        return cls(amount=Decimal(str(amount)), currency=Currency.usd())
```

#### IsoDateTime（`services/shared/domain/value_object/iso_date_time.py`）

ISO 8601 形式の日時を表現する Value Object です。
内部では `datetime` 型を保持し、型安全性を確保します。

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IsoDateTime:
    """日時（ISO 8601 形式）

    Value Object として不変性を保証。
    内部では datetime 型を保持し、型安全性を確保。
    """
    value: datetime

    def __str__(self) -> str:
        return self.value.isoformat()

    @classmethod
    def from_string(cls, s: str) -> "IsoDateTime":
        """ISO 8601 形式の文字列から生成"""
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO 8601 datetime: {s}") from e
        return cls(value=dt)

    def is_before(self, other: "IsoDateTime") -> bool:
        """他の日時より前かどうか"""
        return self.value < other.value

    def is_after(self, other: "IsoDateTime") -> bool:
        """他の日時より後かどうか"""
        return self.value > other.value
```

#### shared/domain/__init__.py の更新

```python
from .entity import Entity, AggregateRoot
from .repository import Repository
from .exception import (
    DomainException,
    ResourceNotFoundException,
    BusinessRuleViolationException,
)
from .value_object import TripId, Currency, Money, IsoDateTime

__all__ = [
    "Entity",
    "AggregateRoot",
    "Repository",
    "DomainException",
    "ResourceNotFoundException",
    "BusinessRuleViolationException",
    "TripId",
    "Currency",
    "Money",
    "IsoDateTime",
]
```

### 3.2 Flight 固有の Value Object

#### BookingId（`services/flight/domain/value_object/booking_id.py`）

```python
from dataclasses import dataclass

from services.shared.domain import TripId


@dataclass(frozen=True)
class BookingId:
    """フライト予約ID（Value Object）

    TripId から派生した冪等なID。
    例: "flight_for_trip-123"
    """
    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_trip_id(cls, trip_id: TripId) -> "BookingId":
        """TripId から冪等な BookingId を生成

        同じ TripId からは常に同じ BookingId が生成される。
        これにより、リトライ時の冪等性が担保される。
        """
        return cls(value=f"flight_for_{trip_id}")
```

#### BookingStatus（`services/flight/domain/enum/booking_status.py`）

```python
from enum import Enum


class BookingStatus(str, Enum):
    """予約ステータス"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
```

#### FlightNumber（`services/flight/domain/value_object/flight_number.py`）

```python
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FlightNumber:
    """フライト番号（Value Object）

    航空会社コード（2文字）+ 便名番号（1-4桁）の形式。
    例: NH001, JL123, AA1234
    """
    value: str

    # フライト番号の形式: 2文字の航空会社コード + 1-4桁の数字
    PATTERN = re.compile(r"^[A-Z]{2}\d{1,4}$")

    def __post_init__(self) -> None:
        normalized = self.value.upper()
        if not self.PATTERN.match(normalized):
            raise ValueError(
                f"Invalid flight number format: {self.value}. "
                "Expected format: AA123 (2 letters + 1-4 digits)"
            )
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value

    @property
    def airline_code(self) -> str:
        """航空会社コード（2文字）"""
        return self.value[:2]

    @property
    def flight_num(self) -> str:
        """便名番号"""
        return self.value[2:]
```

### 3.3 Domain Layer: Booking AggregateRoot

`services/flight/domain/entity/booking.py`

AggregateRoot は Value Object を使用してドメインの概念を表現します。
Repository を持つドメインモデルは AggregateRoot を継承します。

```python
from services.shared.domain import AggregateRoot, TripId, Money, IsoDateTime
from services.shared.domain.exception import BusinessRuleViolationException

from services.flight.domain.enum import BookingStatus
from services.flight.domain.value_object import BookingId, FlightNumber


class Booking(AggregateRoot[BookingId]):
    """フライト予約エンティティ

    AggregateRoot 基底クラスを継承し、BookingId で同一性を判定する。
    全てのフィールドは Value Object で表現される。
    """

    def __init__(
        self,
        id: BookingId,
        trip_id: TripId,
        flight_number: FlightNumber,
        departure_time: IsoDateTime,
        arrival_time: IsoDateTime,
        price: Money,
        status: BookingStatus = BookingStatus.PENDING,
    ) -> None:
        super().__init__(id)
        self._trip_id = trip_id
        self._flight_number = flight_number
        self._departure_time = departure_time
        self._arrival_time = arrival_time
        self._price = price
        self._status = status

        # ドメイン不変条件の検証
        self._validate_schedule()

    def _validate_schedule(self) -> None:
        """出発時刻は到着時刻より前でなければならない"""
        if not self._departure_time.is_before(self._arrival_time):
            raise BusinessRuleViolationException(
                "Departure time must be before arrival time"
            )

    @property
    def trip_id(self) -> TripId:
        return self._trip_id

    @property
    def flight_number(self) -> FlightNumber:
        return self._flight_number

    @property
    def departure_time(self) -> IsoDateTime:
        return self._departure_time

    @property
    def arrival_time(self) -> IsoDateTime:
        return self._arrival_time

    @property
    def price(self) -> Money:
        return self._price

    @property
    def status(self) -> BookingStatus:
        return self._status

    def confirm(self) -> None:
        """予約を確定する"""
        if self._status == BookingStatus.CANCELLED:
            raise BusinessRuleViolationException(
                "Cannot confirm a cancelled booking"
            )
        self._status = BookingStatus.CONFIRMED

    def cancel(self) -> None:
        """予約をキャンセルする（補償トランザクション用）"""
        self._status = BookingStatus.CANCELLED
```

### 3.4 Domain Layer: flight/domain/__init__.py

```python
from .entity import Booking
from .enum import BookingStatus
from .factory import BookingFactory, FlightDetails
from .repository import BookingRepository
from .value_object import BookingId, FlightNumber

__all__ = [
    "Booking",
    "BookingId",
    "BookingStatus",
    "FlightNumber",
    "BookingRepository",
    "BookingFactory",
    "FlightDetails",
]
```

### 3.5 Domain Layer: Repository インターフェース

`services/flight/domain/repository/booking_repository.py`

```python
from abc import abstractmethod
from typing import Optional

from services.shared.domain import Repository, TripId

from services.flight.domain.value_object import BookingId
from services.flight.domain.entity import Booking


class BookingRepository(Repository[Booking, BookingId]):
    """フライト予約リポジトリのインターフェース

    Domain 層で定義し、具象実装は Infrastructure 層で行う。
    これにより、Domain はインフラ（DynamoDB 等）に依存しない。
    """

    @abstractmethod
    def save(self, booking: Booking) -> None:
        """予約を保存する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, booking_id: BookingId) -> Optional[Booking]:
        """予約IDで検索する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_trip_id(self, trip_id: TripId) -> Optional[Booking]:
        """Trip ID で検索する（1 Trip = 1 Flight の前提）"""
        raise NotImplementedError
```

### 3.6 Domain Layer: Factory パターン

`services/flight/domain/factory/booking_factory.py`

Factory はエンティティの生成ロジックをカプセル化します。

```python
from decimal import Decimal
from typing import TypedDict

from services.shared.domain import TripId, Money, Currency, IsoDateTime

from services.flight.domain.entity import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.value_object import BookingId, FlightNumber


class FlightDetails(TypedDict):
    """フライト詳細の入力データ構造"""
    flight_number: str
    departure_time: str
    arrival_time: str
    price_amount: Decimal
    price_currency: str


class BookingFactory:
    """フライト予約エンティティのファクトリ

    - 冪等性を担保する ID 生成
    - プリミティブ型から Value Object への変換
    - 初期状態の設定
    """

    def create(self, trip_id: TripId, flight_details: FlightDetails) -> Booking:
        """新規予約エンティティを生成する

        Args:
            trip_id: 旅行ID（Value Object）
            flight_details: フライト詳細情報

        Returns:
            Booking: 生成された予約エンティティ（PENDING状態）
        """
        # 冪等性担保: 同じ TripId からは常に同じ BookingId を生成
        booking_id = BookingId.from_trip_id(trip_id)

        # プリミティブ型から Value Object に変換
        flight_number = FlightNumber(flight_details["flight_number"])
        departure_time = IsoDateTime.from_string(flight_details["departure_time"])
        arrival_time = IsoDateTime.from_string(flight_details["arrival_time"])
        price = Money(
            amount=flight_details["price_amount"],
            currency=Currency(flight_details["price_currency"]),
        )

        return Booking(
            id=booking_id,
            trip_id=trip_id,
            flight_number=flight_number,
            departure_time=departure_time,
            arrival_time=arrival_time,
            price=price,
            status=BookingStatus.PENDING,
        )
```

### 3.7 Infrastructure Layer: DynamoDB Repository 実装

#### 3.7.1 基本実装

`services/flight/infrastructure/dynamodb_booking_repository.py`

```python
import os
from typing import Optional
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from services.shared.domain import TripId, Money, Currency, IsoDateTime
from services.shared.domain.exception import DuplicateResourceException

from services.flight.domain.entity import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.value_object import BookingId, FlightNumber
from services.flight.domain.repository import BookingRepository


class DynamoDBBookingRepository(BookingRepository):
    """DynamoDB を使用した BookingRepository の具象実装"""

    def __init__(self, table_name: Optional[str] = None) -> None:
        self.table_name = table_name or os.getenv("TABLE_NAME")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def save(self, booking: Booking) -> None:
        """予約を DynamoDB に保存する

        Infrastructure層の責務として、Entity から DynamoDB アイテムへの変換をここで行う。
        Entity は永続化形式を知らないため、Repository が変換を担当する。

        条件付き書き込みにより、同一キーのアイテムが既に存在する場合は
        DuplicateResourceException を発生させる。
        """
        item = {
            "PK": f"TRIP#{booking.trip_id}",
            "SK": f"FLIGHT#{booking.id}",
            "entity_type": "FLIGHT",
            "booking_id": str(booking.id),
            "trip_id": str(booking.trip_id),
            "flight_number": str(booking.flight_number),
            "departure_time": str(booking.departure_time),
            "arrival_time": str(booking.arrival_time),
            "price_amount": str(booking.price.amount),
            "price_currency": str(booking.price.currency),
            "status": booking.status.value,
        }

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(PK)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DuplicateResourceException(
                    f"Booking already exists: {booking.id}"
                )
            raise

    def find_by_id(self, booking_id: BookingId) -> Optional[Booking]:
        """予約IDで検索する（GSI が必要、今回は未実装）"""
        raise NotImplementedError("GSI required for this query")

    def find_by_trip_id(self, trip_id: TripId) -> Optional[Booking]:
        """Trip ID でフライト予約を検索する"""
        response = self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": f"TRIP#{trip_id}",
                ":sk_prefix": "FLIGHT#",
            },
        )

        items = response.get("Items", [])
        if not items:
            return None

        item = items[0]
        return self._to_entity(item)

    def _to_entity(self, item: dict) -> Booking:
        """DynamoDB アイテムをドメインエンティティに変換する"""
        return Booking(
            id=BookingId(value=item["booking_id"]),
            trip_id=TripId(value=item["trip_id"]),
            flight_number=FlightNumber(value=item["flight_number"]),
            departure_time=IsoDateTime.from_string(item["departure_time"]),
            arrival_time=IsoDateTime.from_string(item["arrival_time"]),
            price=Money(
                amount=Decimal(item["price_amount"]),
                currency=Currency(item["price_currency"]),
            ),
            status=BookingStatus(item["status"]),
        )
```

#### 3.7.2 条件付き書き込みによる重複防止

上記の `save` メソッドでは、DynamoDB の**条件付き書き込み**を使用しています。

##### なぜ条件付き書き込みが必要か

通常の `put_item` は無条件でアイテムを上書きします。これには以下の問題があります：

- **重複リクエスト**: ネットワーク障害等でリトライが発生した場合、同じデータが複数回書き込まれる可能性
- **データ整合性**: Saga パターンでは冪等性が重要。同一リクエストの重複実行時にデータ整合性を保証する必要がある

##### `attribute_not_exists` の動作

```python
self.table.put_item(
    Item=item,
    ConditionExpression="attribute_not_exists(PK)",
)
```

- `attribute_not_exists(PK)`: PK 属性が存在しない場合のみ書き込みを許可
- 既にアイテムが存在する場合、`ConditionalCheckFailedException` が発生
- これにより「新規作成のみ許可、上書き禁止」を実現

##### エラーハンドリング

```python
except ClientError as e:
    if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
        raise DuplicateResourceException(
            f"Booking already exists: {booking.id}"
        )
    raise
```

- `ConditionalCheckFailedException` をキャッチし、ドメイン層の例外に変換
- その他のエラー（ネットワーク障害等）は再送出

##### 発展: 楽観的ロック

本ハンズオンでは「新規作成時の重複防止」のみを扱いますが、更新処理では**楽観的ロック**（バージョン管理）が有効です：

```python
# 更新時の例（本ハンズオンの範囲外）
self.table.put_item(
    Item={**item, "version": new_version},
    ConditionExpression="version = :expected_version",
    ExpressionAttributeValues={":expected_version": current_version},
)
```

これにより、同時更新による競合を検出できます。

#### 3.7.3 例外クラスの追加

`services/shared/domain/exception/exceptions.py` に `DuplicateResourceException` を追加します。

```python
class DomainException(Exception):
    """ドメイン層で発生する基底例外"""

    pass


class ResourceNotFoundException(DomainException):
    """リソースが見つからない場合"""

    pass


class BusinessRuleViolationException(DomainException):
    """ビジネスルールに違反した場合"""

    pass


class DuplicateResourceException(DomainException):
    """リソースの重複エラー（条件付き書き込みの失敗時）"""

    pass
```

`shared/domain/__init__.py` の更新も忘れずに行います：

```python
from .exception import (
    DomainException,
    ResourceNotFoundException,
    BusinessRuleViolationException,
    DuplicateResourceException,  # 追加
)
```

### 3.8 Application Layer: 予約ユースケース

`services/flight/applications/reserve_flight.py`

```python
from services.shared.domain import TripId

from services.flight.domain.entity import Booking
from services.flight.domain.factory import BookingFactory, FlightDetails
from services.flight.domain.repository import BookingRepository


class ReserveFlightService:
    """フライト予約ユースケース

    Factory と Repository を使用してエンティティの生成・永続化を行う。
    具象実装ではなく抽象に依存することで、テスト容易性を確保。
    """

    def __init__(
        self,
        repository: BookingRepository,
        factory: BookingFactory,
    ) -> None:
        self._repository = repository
        self._factory = factory

    def reserve(self, trip_id: TripId, flight_details: FlightDetails) -> Booking:
        """フライトを予約する

        Args:
            trip_id: 旅行ID（Value Object）
            flight_details: フライト詳細情報

        Returns:
            Booking: 予約エンティティ（Handler層でレスポンス形式に変換する）
        """
        # 1. Factory でエンティティを生成（ID生成・Value Object変換はFactoryに委譲）
        booking: Booking = self._factory.create(trip_id, flight_details)

        # 2. Repository で永続化
        self._repository.save(booking)

        # 3. Entity を返却（レスポンス形式への変換は Handler 層の責務）
        return booking
```

### 3.9 Handler Layer: リクエストバリデーション

`services/flight/handlers/request_models.py`

**Pydantic** を使用して入力スキーマを定義します。
Handler 層でプリミティブ型を受け取り、Application 層に渡す前に Value Object に変換します。

```python
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class FlightDetailsRequest(BaseModel):
    """フライト詳細のリクエストモデル"""

    flight_number: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="フライト番号（例: NH001）",
        examples=["NH001", "JL123"],
    )
    departure_time: str = Field(
        ...,
        description="出発時刻（ISO 8601形式）",
        examples=["2024-01-01T10:00:00"],
    )
    arrival_time: str = Field(
        ...,
        description="到着時刻（ISO 8601形式）",
        examples=["2024-01-01T12:00:00"],
    )
    price_amount: Decimal = Field(
        ...,
        gt=0,
        description="料金（0より大きい値）",
        examples=[50000],
    )
    price_currency: str = Field(
        default="JPY",
        pattern="^[A-Z]{3}$",
        description="通貨コード（ISO 4217）",
        examples=["JPY", "USD"],
    )

    @field_validator("price_amount", mode="before")
    @classmethod
    def convert_price_to_decimal(cls, v):
        """文字列や数値を Decimal に変換"""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class ReserveFlightRequest(BaseModel):
    """フライト予約リクエストモデル"""

    trip_id: str = Field(
        ...,
        min_length=1,
        description="旅行ID",
        examples=["trip-123"],
    )
    flight_details: FlightDetailsRequest

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "trip_id": "trip-123",
                    "flight_details": {
                        "flight_number": "NH001",
                        "departure_time": "2024-01-01T10:00:00",
                        "arrival_time": "2024-01-01T12:00:00",
                        "price_amount": 50000,
                        "price_currency": "JPY",
                    },
                }
            ]
        }
    }
```

### 3.10 Handler Layer: Lambda エントリーポイント

`services/flight/handlers/reserve.py`

Handler 層では責務ごとにメソッドを分割し、`lambda_handler` をシンプルに保ちます。

```python
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel

from services.shared.domain import TripId

from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.domain.entity import Booking
from services.flight.domain.factory import FlightDetails
from services.flight.infrastructure.dynamodb_booking_repository import DynamoDBBookingRepository
from services.flight.domain.factory import BookingFactory
from services.flight.handlers.request_models import ReserveFlightRequest

logger = Logger()


# =============================================================================
# レスポンスモデル（Pydantic）
# =============================================================================
class BookingData(BaseModel):
    """予約データのレスポンスモデル"""

    booking_id: str
    trip_id: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price_amount: str
    price_currency: str
    status: str


class SuccessResponse(BaseModel):
    """成功レスポンスモデル"""

    status: str = "success"
    data: BookingData


class ErrorResponse(BaseModel):
    """エラーレスポンスモデル"""

    status: str = "error"
    error_code: str
    message: str
    details: list | None = None


# =============================================================================
# 依存関係の組み立て（Composition Root）
# Lambda のコールドスタート時に一度だけ実行され、インスタンスが再利用される
# =============================================================================
repository = DynamoDBBookingRepository()
factory = BookingFactory()
service = ReserveFlightService(repository=repository, factory=factory)


# =============================================================================
# ヘルパー関数
# =============================================================================
def _to_flight_details(request: ReserveFlightRequest) -> FlightDetails:
    """リクエストから FlightDetails 辞書を構築"""
    return {
        "flight_number": request.flight_details.flight_number,
        "departure_time": request.flight_details.departure_time,
        "arrival_time": request.flight_details.arrival_time,
        "price_amount": request.flight_details.price_amount,
        "price_currency": request.flight_details.price_currency,
    }


def _to_response(booking: Booking) -> dict:
    """Entity をレスポンス形式に変換"""
    return SuccessResponse(
        data=BookingData(
            booking_id=str(booking.id),
            trip_id=str(booking.trip_id),
            flight_number=str(booking.flight_number),
            departure_time=str(booking.departure_time),
            arrival_time=str(booking.arrival_time),
            price_amount=str(booking.price.amount),
            price_currency=str(booking.price.currency),
            status=booking.status.value,
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
@event_parser(model=ReserveFlightRequest)
def lambda_handler(event: ReserveFlightRequest, context: LambdaContext) -> dict:
    """フライト予約 Lambda ハンドラ

    Step Functions からの入力を受け取り、
    @event_parser デコレータで自動バリデーション後、フライト予約処理を実行する。
    バリデーションエラーは ValidationError として raise され、Step Functions でハンドリング可能。
    """
    logger.info("Received reserve flight request")

    try:
        trip_id = TripId(value=event.trip_id)
        flight_details = _to_flight_details(event)
        booking = service.reserve(trip_id, flight_details)
        return _to_response(booking)

    except Exception as e:
        logger.exception("Failed to reserve flight")
        return _error_response("INTERNAL_ERROR", str(e))
```

### 3.11 バリデーションエラーのレスポンス例

入力が不正な場合、以下のような構造化されたエラーレスポンスが返されます。

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "入力データが不正です",
  "details": [
    {
      "type": "string_too_short",
      "loc": ["flight_details", "flight_number"],
      "msg": "String should have at least 2 characters",
      "input": "X"
    },
    {
      "type": "greater_than",
      "loc": ["flight_details", "price_amount"],
      "msg": "Input should be greater than 0",
      "input": -100
    }
  ]
}
```

## 4. 単体テストの実装 (Unit Testing)

デプロイ前にロジックを検証するため、テストを作成します。
Repository パターンを採用したことで、**DynamoDB への依存なしにビジネスロジックをテスト**できます。

### 4.1 テストファイルの配置

Value Object と Entity を分離したことで、テストも細かく分割できます。

```
tests/unit/services/
├── shared/
│   └── domain/
│       └── value_object/
│           ├── __init__.py
│           ├── test_trip_id.py
│           ├── test_money.py
│           ├── test_currency.py
│           └── test_iso_date_time.py
└── flight/
    ├── __init__.py
    ├── domain/
    │   ├── entity/
    │   │   ├── __init__.py
    │   │   └── test_booking.py
    │   └── value_object/
    │       ├── __init__.py
    │       ├── test_booking_id.py
    │       └── test_flight_number.py
    ├── test_booking_factory.py
    ├── test_request_models.py
    └── test_reserve_flight.py
```

### 4.2 Value Object のテスト（`test_flight_number.py`）

```python
import pytest

from services.flight.domain.value_object import FlightNumber


class TestFlightNumber:
    """FlightNumber Value Object のテスト"""

    def test_valid_flight_number(self):
        """正常なフライト番号を生成できる"""
        flight_number = FlightNumber("NH001")
        assert flight_number.value == "NH001"
        assert flight_number.airline_code == "NH"
        assert flight_number.flight_num == "001"

    def test_lowercase_is_normalized(self):
        """小文字は大文字に正規化される"""
        flight_number = FlightNumber("nh001")
        assert flight_number.value == "NH001"

    def test_invalid_format_raises_error(self):
        """不正な形式はエラーになる"""
        with pytest.raises(ValueError):
            FlightNumber("INVALID")
```

### 4.3 Entity のテスト（`test_booking.py`）

pytest の「Factories as fixtures」パターンを使用して、テストデータ生成用の fixture を定義します。
fixture から**関数（Factory）を返す**ことで、テストごとにパラメータを柔軟に変更できます。

参考: https://docs.pytest.org/en/stable/how-to/fixtures.html#factories-as-fixtures

```python
import pytest
from decimal import Decimal

from services.shared.domain import TripId, Money, Currency, IsoDateTime
from services.shared.domain.exception import BusinessRuleViolationException

from services.flight.domain.entity import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.value_object import BookingId, FlightNumber


@pytest.fixture
def create_booking():
    """Booking を生成する Factory を返す fixture

    Factories as fixtures パターン:
    オブジェクトそのものではなく「オブジェクトを作る関数」を返すことで、
    テストごとにパラメータを柔軟に変更できる。
    """
    def _factory(
        status: BookingStatus = BookingStatus.PENDING,
        booking_id: str = "test-id",
        trip_id: str = "trip-123",
        flight_number: str = "NH001",
        departure_time: str = "2024-01-01T10:00:00",
        arrival_time: str = "2024-01-01T12:00:00",
        price_amount: Decimal = Decimal("50000"),
    ) -> Booking:
        return Booking(
            id=BookingId(value=booking_id),
            trip_id=TripId(value=trip_id),
            flight_number=FlightNumber(value=flight_number),
            departure_time=IsoDateTime.from_string(departure_time),
            arrival_time=IsoDateTime.from_string(arrival_time),
            price=Money(amount=price_amount, currency=Currency.jpy()),
            status=status,
        )
    return _factory


class TestBooking:
    """Booking Entity のテスト"""

    def test_confirm_pending_booking(self, create_booking):
        """PENDING 状態の予約を確定できる"""
        booking = create_booking(status=BookingStatus.PENDING)
        booking.confirm()
        assert booking.status == BookingStatus.CONFIRMED

    def test_cannot_confirm_cancelled_booking(self, create_booking):
        """CANCELLED 状態の予約は確定できない"""
        booking = create_booking(status=BookingStatus.CANCELLED)
        with pytest.raises(BusinessRuleViolationException):
            booking.confirm()

    def test_invalid_schedule_raises_error(self):
        """出発時刻が到着時刻より後の場合はエラー"""
        with pytest.raises(BusinessRuleViolationException):
            Booking(
                id=BookingId(value="test-id"),
                trip_id=TripId(value="trip-123"),
                flight_number=FlightNumber(value="NH001"),
                departure_time=IsoDateTime.from_string("2024-01-01T12:00:00"),  # 後
                arrival_time=IsoDateTime.from_string("2024-01-01T10:00:00"),    # 前
                price=Money(amount=Decimal("50000"), currency=Currency.jpy()),
            )
```

### 4.4 Application Service のテスト（`test_reserve_flight.py`）

```python
from decimal import Decimal
from unittest.mock import MagicMock

from services.shared.domain import TripId

from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.domain.entity import Booking
from services.flight.domain.enum import BookingStatus
from services.flight.domain.factory import BookingFactory


class TestReserveFlightService:
    """ReserveFlightService のテスト"""

    def test_reserve_creates_and_saves_booking(self):
        """予約が作成され、Repository に保存され、Entity が返される"""
        # Arrange
        mock_repository = MagicMock()
        factory = BookingFactory()
        service = ReserveFlightService(
            repository=mock_repository,
            factory=factory,
        )

        trip_id = TripId(value="trip-123")
        flight_details = {
            "flight_number": "NH001",
            "departure_time": "2024-01-01T10:00:00",
            "arrival_time": "2024-01-01T12:00:00",
            "price_amount": Decimal("50000"),
            "price_currency": "JPY",
        }

        # Act
        booking = service.reserve(trip_id, flight_details)

        # Assert: Entity が返されること
        assert isinstance(booking, Booking)
        assert booking.trip_id == trip_id
        assert booking.status == BookingStatus.PENDING

        # Assert: Repository.save が呼ばれたこと
        mock_repository.save.assert_called_once()
        saved_booking = mock_repository.save.call_args[0][0]
        assert saved_booking == booking
```

### 4.5 テストの実行

```bash
# 共通 Value Object のテストを実行
pytest tests/unit/services/shared/ -v

# Flight Service のテストを実行
pytest tests/unit/services/flight/ -v

# カバレッジ付きで実行
pytest tests/unit/services/flight/ --cov=services.flight
```

## 5. CDK Construct への定義追加

実装した Lambda 関数を管理する Construct を作成します。

### ファイル構成
```
infra/
├── constructs/
│   ├── __init__.py
│   ├── database.py      # Hands-on 02 で作成済み
│   ├── layers.py        # Hands-on 03 で作成済み
│   └── functions.py     # Lambda Functions Construct (今回追加)
```

### infra/constructs/functions.py
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
        # Flight Service Lambda
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

        # DynamoDB への読み書き権限を付与
        table.grant_read_write_data(self.flight_reserve)
```

### infra/constructs/\_\_init\_\_.py (更新)
```python
from .database import Database
from .layers import Layers
from .functions import Functions

__all__ = ["Database", "Layers", "Functions"]
```

### serverless_trip_saga_stack.py (更新)
```python
from aws_cdk import Stack
from constructs import Construct
from infra.constructs import Database, Layers, Functions


class ServerlessTripSagaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Database Construct
        database = Database(self, "Database")

        # Layers Construct
        layers = Layers(self, "Layers")

        # Functions Construct
        functions = Functions(
            self, "Functions",
            table=database.table,
            common_layer=layers.common_layer,
        )
```

## 6. デプロイと動作確認

```bash
cdk deploy
```

デプロイ後、AWS CLI または Lambda コンソールの「テスト」機能を使って関数を実行し、DynamoDB にデータが保存されることを確認します。

## 7. 次のステップ

Flight Service の基本実装が完了しました。
次は、同様のパターンで他のサービスを効率的に実装します。

👉 **[Hands-on 05: Service Implementation - Hotel & Payment](./05-service-implementation-hotel-payment.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/flight-service`
*   **コミットメッセージ**: `Flightサービスの実装`
