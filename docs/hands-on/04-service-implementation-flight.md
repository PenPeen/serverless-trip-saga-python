# Hands-on 04: Service Implementation - Flight

本ハンズオンでは、最初のマイクロサービスである **Flight Service** (フライト予約) を実装します。
DDD (ドメイン駆動設計) のレイヤー構造を適用し、Hands-on 03 で作成した DDD Building Blocks を活用します。

## 1. 目的
*   DDD レイヤー (Handler, Application, Domain, Adapter) に基づいた Lambda 実装を行う。
*   **Repository パターン** を適用し、永続化を抽象化する。
*   **Factory パターン** を適用し、エンティティ生成ロジックを分離する。
*   `pytest` を用いた単体テストを作成し、ロジックの正当性を検証する。
*   DynamoDB へのデータ書き込みを実装する。

## 2. ディレクトリ構造
`services/flight/` 配下に以下の構造を作成します。

```
services/flight/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── request_models.py   # Pydantic リクエストモデル（バリデーション）
│   └── reserve.py          # Lambda エントリーポイント
├── applications/
│   ├── __init__.py
│   └── reserve_flight.py   # ユースケース
├── domain/
│   ├── __init__.py
│   ├── booking.py          # Entity & ValueObject
│   ├── booking_factory.py  # Factory (ID生成ロジック)
│   └── booking_repository.py  # Repository インターフェース (ABC)
└── adapters/
    ├── __init__.py
    └── dynamodb_booking_repository.py  # Repository 具象実装
```

## 3. 実装ステップ

### 3.1 Domain Layer: フライト予約モデル (Entity & ValueObject)

`services/flight/domain/booking.py` を作成し、以下のコードを実装します。

Hands-on 03 で作成した `Entity` 基底クラスを継承し、**振る舞いを持つドメインモデル**を構築します。

```python
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

from services.shared.domain import Entity
from services.shared.domain.exceptions import BusinessRuleViolationException


# Value Object: 予約ステータス
class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


# Value Object: 予約ID（不変）
@dataclass(frozen=True)
class BookingId:
    value: str

    def __str__(self) -> str:
        return self.value


# Entity: フライト予約
@dataclass
class Booking(Entity[BookingId]):
    """フライト予約エンティティ

    Entity基底クラスを継承し、BookingIdで同一性を判定する。
    """

    trip_id: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price: Decimal
    status: BookingStatus = field(default=BookingStatus.PENDING)

    def __post_init__(self) -> None:
        # Entity基底クラスの初期化（IDの設定）
        # dataclass継承時は __post_init__ で親の初期化を行う
        pass

    @property
    def id(self) -> BookingId:
        return self._id

    # ドメインメソッド: 予約確定 (振る舞いの実装)
    def confirm(self) -> None:
        if self.status == BookingStatus.CANCELLED:
            raise BusinessRuleViolationException(
                "Cannot confirm a cancelled booking"
            )
        self.status = BookingStatus.CONFIRMED

    # ドメインメソッド: キャンセル
    def cancel(self) -> None:
        if self.status == BookingStatus.CONFIRMED:
            # 確定済みの予約もキャンセル可能（補償トランザクション用）
            pass
        self.status = BookingStatus.CANCELLED

    def to_dict(self) -> dict:
        """永続化用の辞書表現を返す"""
        return {
            "booking_id": str(self._id),
            "trip_id": self.trip_id,
            "flight_number": self.flight_number,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "price": str(self.price),
            "status": self.status.value,
        }
```

### 3.2 Domain Layer: Repository インターフェース

`services/flight/domain/booking_repository.py` を作成します。

Repository の抽象インターフェースを Domain 層に定義することで、**依存性逆転の原則（DIP）** を適用します。
Application 層は具象実装（DynamoDB）ではなく、この抽象に依存します。

```python
from abc import abstractmethod
from typing import Optional

from services.shared.domain import Repository
from services.flight.domain.booking import Booking, BookingId


class BookingRepository(Repository[Booking, BookingId]):
    """フライト予約リポジトリのインターフェース

    Domain層で定義し、具象実装はAdapter層で行う。
    これにより、Domainはインフラ（DynamoDB等）に依存しない。
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
    def find_by_trip_id(self, trip_id: str) -> Optional[Booking]:
        """Trip IDで検索する（1 Trip = 1 Flight の前提）"""
        raise NotImplementedError
```

### 3.3 Domain Layer: Factory パターン

`services/flight/domain/booking_factory.py` を作成します。

Factory はエンティティの生成ロジックをカプセル化します。
特に **冪等性キーの生成**（同じ trip_id からは常に同じ booking_id を生成）はここで行います。

```python
from decimal import Decimal
from typing import TypedDict

from services.flight.domain.booking import Booking, BookingId, BookingStatus


class FlightDetails(TypedDict):
    """フライト詳細の入力データ構造"""
    flight_number: str
    departure_time: str
    arrival_time: str
    price: Decimal


class BookingFactory:
    """フライト予約エンティティのファクトリ

    - 冪等性を担保するID生成
    - 初期状態の設定
    - 生成時のバリデーション
    """

    def create(self, trip_id: str, flight_details: FlightDetails) -> Booking:
        """新規予約エンティティを生成する

        Args:
            trip_id: 旅行ID
            flight_details: フライト詳細情報

        Returns:
            Booking: 生成された予約エンティティ（PENDING状態）
        """
        # 冪等性担保: 同じ trip_id からは常に同じ booking_id を生成
        # これにより、リトライ時も同じエンティティが生成される
        booking_id = BookingId(value=f"flight_for_{trip_id}")

        return Booking(
            _id=booking_id,
            trip_id=trip_id,
            flight_number=flight_details["flight_number"],
            departure_time=flight_details["departure_time"],
            arrival_time=flight_details["arrival_time"],
            price=flight_details["price"],
            status=BookingStatus.PENDING,
        )
```

### 3.4 Adapter Layer: DynamoDB Repository 実装

`services/flight/adapters/dynamodb_booking_repository.py` を作成します。

Domain 層で定義した `BookingRepository` インターフェースを実装します。
**ドメインオブジェクトと DynamoDB アイテムの変換**はここで行います。

```python
import os
from typing import Optional
from decimal import Decimal

import boto3

from services.flight.domain.booking import Booking, BookingId, BookingStatus
from services.flight.domain.booking_repository import BookingRepository


class DynamoDBBookingRepository(BookingRepository):
    """DynamoDB を使用した BookingRepository の具象実装"""

    def __init__(self, table_name: Optional[str] = None) -> None:
        self.table_name = table_name or os.getenv("TABLE_NAME")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def save(self, booking: Booking) -> None:
        """予約を DynamoDB に保存する"""
        item = {
            "PK": f"TRIP#{booking.trip_id}",
            "SK": f"FLIGHT#{booking.id}",
            "entity_type": "FLIGHT",
            **booking.to_dict(),
        }
        self.table.put_item(Item=item)

    def find_by_id(self, booking_id: BookingId) -> Optional[Booking]:
        """予約IDで検索する（GSI が必要、今回は未実装）"""
        # 実装は GSI 設計後に追加
        raise NotImplementedError("GSI required for this query")

    def find_by_trip_id(self, trip_id: str) -> Optional[Booking]:
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
            _id=BookingId(value=item["booking_id"]),
            trip_id=item["trip_id"],
            flight_number=item["flight_number"],
            departure_time=item["departure_time"],
            arrival_time=item["arrival_time"],
            price=Decimal(item["price"]),
            status=BookingStatus(item["status"]),
        )
```

### 3.5 Application Layer: 予約ユースケース

`services/flight/applications/reserve_flight.py` を作成します。

アプリケーションサービスは、**Factory** でエンティティを生成し、**Repository** で永続化を行います。
具象クラスではなく**抽象（インターフェース）に依存**させることで、テスト時にモックへの差し替えが容易になります。

```python
from services.flight.domain.booking import Booking
from services.flight.domain.booking_factory import BookingFactory, FlightDetails
from services.flight.domain.booking_repository import BookingRepository


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

    def reserve(self, trip_id: str, flight_details: FlightDetails) -> dict:
        """フライトを予約する

        Args:
            trip_id: 旅行ID
            flight_details: フライト詳細情報

        Returns:
            dict: 予約結果
        """
        # 1. Factory でエンティティを生成（ID生成ロジックはFactoryに委譲）
        booking: Booking = self._factory.create(trip_id, flight_details)

        # 2. ドメインロジックの実行（必要に応じて）
        # 例: booking.validate_schedule()

        # 3. Repository で永続化
        self._repository.save(booking)

        # 4. 結果の返却
        return booking.to_dict()
```

### 3.6 Handler Layer: リクエストバリデーション

`services/flight/handlers/request_models.py` を作成します。

**Pydantic** を使用して入力スキーマを厳密に定義します。
これにより、型変換・バリデーション・エラーメッセージ生成が自動化されます。

```python
from decimal import Decimal
from typing import Optional

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
    price: Decimal = Field(
        ...,
        gt=0,
        description="料金（0より大きい値）",
        examples=[50000],
    )

    @field_validator("price", mode="before")
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
                        "price": 50000,
                    },
                }
            ]
        }
    }
```

### 3.7 Handler Layer: Lambda エントリーポイント

`services/flight/handlers/reserve.py` を作成します。

Handler は Pydantic でバリデーションを行い、エラー時は構造化されたレスポンスを返します。

```python
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.adapters.dynamodb_booking_repository import DynamoDBBookingRepository
from services.flight.domain.booking_factory import BookingFactory
from services.flight.handlers.request_models import ReserveFlightRequest

logger = Logger()
tracer = Tracer()

# =============================================================================
# 依存関係の組み立て（Composition Root）
# Lambda のコールドスタート時に一度だけ実行され、インスタンスが再利用される
# =============================================================================
repository = DynamoDBBookingRepository()
factory = BookingFactory()
service = ReserveFlightService(repository=repository, factory=factory)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """フライト予約 Lambda ハンドラ

    Step Functions または API Gateway からの入力を受け取り、
    Pydantic でバリデーション後、フライト予約処理を実行する。
    """
    logger.info("Received reserve flight request", extra={"event": event})

    # =========================================================================
    # 1. 入力バリデーション（Pydantic）
    # =========================================================================
    try:
        request = ReserveFlightRequest.model_validate(event)
    except ValidationError as e:
        logger.warning("Validation failed", extra={"errors": e.errors()})
        return {
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "入力データが不正です",
            "details": e.errors(),
        }

    # =========================================================================
    # 2. Application Service 呼び出し
    # =========================================================================
    try:
        # Pydantic Model から FlightDetails 辞書に変換
        flight_details = {
            "flight_number": request.flight_details.flight_number,
            "departure_time": request.flight_details.departure_time,
            "arrival_time": request.flight_details.arrival_time,
            "price": request.flight_details.price,
        }

        result = service.reserve(request.trip_id, flight_details)

        return {
            "status": "success",
            "data": result,
        }

    except Exception as e:
        logger.exception("Failed to reserve flight")
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": str(e),
        }
```

### 3.8 バリデーションエラーのレスポンス例

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
      "loc": ["flight_details", "price"],
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

```
tests/unit/services/flight/
├── __init__.py
├── test_booking.py           # Entity のテスト
├── test_booking_factory.py   # Factory のテスト
├── test_request_models.py    # リクエストバリデーションのテスト
└── test_reserve_flight.py    # Application Service のテスト
```

### 4.2 リクエストバリデーションのテスト (`test_request_models.py`)

Pydantic モデルのバリデーションをテストします。

```python
import pytest
from decimal import Decimal
from pydantic import ValidationError

from services.flight.handlers.request_models import (
    FlightDetailsRequest,
    ReserveFlightRequest,
)


class TestFlightDetailsRequest:
    """FlightDetailsRequest のバリデーションテスト"""

    def test_valid_request(self):
        """正常なリクエストはバリデーションを通過する"""
        request = FlightDetailsRequest(
            flight_number="NH001",
            departure_time="2024-01-01T10:00:00",
            arrival_time="2024-01-01T12:00:00",
            price=50000,
        )
        assert request.flight_number == "NH001"
        assert request.price == Decimal("50000")

    def test_price_string_converted_to_decimal(self):
        """文字列の price は Decimal に変換される"""
        request = FlightDetailsRequest(
            flight_number="NH001",
            departure_time="2024-01-01T10:00:00",
            arrival_time="2024-01-01T12:00:00",
            price="50000.50",
        )
        assert request.price == Decimal("50000.50")

    def test_flight_number_too_short(self):
        """flight_number が短すぎる場合はエラー"""
        with pytest.raises(ValidationError) as exc_info:
            FlightDetailsRequest(
                flight_number="X",  # 2文字未満
                departure_time="2024-01-01T10:00:00",
                arrival_time="2024-01-01T12:00:00",
                price=50000,
            )
        assert "string_too_short" in str(exc_info.value)

    def test_price_must_be_positive(self):
        """price は0より大きい必要がある"""
        with pytest.raises(ValidationError) as exc_info:
            FlightDetailsRequest(
                flight_number="NH001",
                departure_time="2024-01-01T10:00:00",
                arrival_time="2024-01-01T12:00:00",
                price=-100,
            )
        assert "greater_than" in str(exc_info.value)

    def test_missing_required_field(self):
        """必須フィールドが欠けている場合はエラー"""
        with pytest.raises(ValidationError) as exc_info:
            FlightDetailsRequest(
                flight_number="NH001",
                # departure_time が欠けている
                arrival_time="2024-01-01T12:00:00",
                price=50000,
            )
        assert "departure_time" in str(exc_info.value)
```

### 4.3 Entity のテスト (`test_booking.py`)

```python
import pytest
from decimal import Decimal

from services.flight.domain.booking import Booking, BookingId, BookingStatus
from services.shared.domain.exceptions import BusinessRuleViolationException


class TestBooking:
    """Booking Entity のテスト"""

    def test_confirm_pending_booking(self):
        """PENDING状態の予約を確定できる"""
        booking = Booking(
            _id=BookingId(value="test-id"),
            trip_id="trip-123",
            flight_number="NH001",
            departure_time="2024-01-01T10:00:00",
            arrival_time="2024-01-01T12:00:00",
            price=Decimal("50000"),
            status=BookingStatus.PENDING,
        )

        booking.confirm()

        assert booking.status == BookingStatus.CONFIRMED

    def test_cannot_confirm_cancelled_booking(self):
        """CANCELLED状態の予約は確定できない"""
        booking = Booking(
            _id=BookingId(value="test-id"),
            trip_id="trip-123",
            flight_number="NH001",
            departure_time="2024-01-01T10:00:00",
            arrival_time="2024-01-01T12:00:00",
            price=Decimal("50000"),
            status=BookingStatus.CANCELLED,
        )

        with pytest.raises(BusinessRuleViolationException):
            booking.confirm()
```

### 4.4 Application Service のテスト (`test_reserve_flight.py`)

Repository を**モック**に差し替えることで、DynamoDB なしでテストできます。

```python
from decimal import Decimal
from unittest.mock import MagicMock

from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.domain.booking import Booking, BookingId, BookingStatus
from services.flight.domain.booking_factory import BookingFactory


class TestReserveFlightService:
    """ReserveFlightService のテスト"""

    def test_reserve_creates_and_saves_booking(self):
        """予約が作成され、Repositoryに保存される"""
        # Arrange: モックの準備
        mock_repository = MagicMock()
        factory = BookingFactory()
        service = ReserveFlightService(
            repository=mock_repository,
            factory=factory,
        )

        flight_details = {
            "flight_number": "NH001",
            "departure_time": "2024-01-01T10:00:00",
            "arrival_time": "2024-01-01T12:00:00",
            "price": Decimal("50000"),
        }

        # Act: 予約実行
        result = service.reserve("trip-123", flight_details)

        # Assert: Repository.save が呼ばれたことを確認
        mock_repository.save.assert_called_once()

        # 保存されたエンティティの検証
        saved_booking = mock_repository.save.call_args[0][0]
        assert isinstance(saved_booking, Booking)
        assert saved_booking.trip_id == "trip-123"
        assert saved_booking.status == BookingStatus.PENDING
```

### 4.5 テストの実行

```bash
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