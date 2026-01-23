# Hands-on 04: Service Implementation - Flight

本ハンズオンでは、最初のマイクロサービスである **Flight Service** (フライト予約) を実装します。
DDD (ドメイン駆動設計) のレイヤー構造を適用し、単体テストを用いた開発サイクルを実践します。

## 1. 目的
*   DDD レイヤー (Handler, Application, Domain, Adapter) に基づいた Lambda 実装を行う。
*   `pytest` を用いた単体テストを作成し、ロジックの正当性を検証する。
*   DynamoDB へのデータ書き込みを実装する。

## 2. ディレクトリ構造の復習
`services/flight/` 配下に以下の構造を作成済みです。

*   `handlers/`: Lambda ハンドラ (入力受け取り、レスポンス返却)
*   `applications/`: ユースケース (ドメインオブジェクトの操作、リポジトリの呼び出し)
*   `domain/`: ドメインモデル (ビジネスルール、バリデーション)
*   `adapters/`: インフラ実装 (DynamoDB クライアント)

## 3. 実装ステップ

### 3.1 Domain Layer: フライト予約モデル (DDD: Entity & ValueObject)
`services/flight/domain/booking.py` を作成し、以下のコードを実装します。

ここでは、単純なデータクラスではなく、**振る舞いを持つドメインモデル**を構築します。

```python
from enum import Enum
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

# Value Object: 予約ステータス
class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

# Value Object: 予約ID
class BookingID(BaseModel):
    value: str

# Entity: フライト予約
class Booking(BaseModel):
    booking_id: BookingID
    trip_id: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price: Decimal
    status: BookingStatus = BookingStatus.PENDING

    # ドメインメソッド: 予約確定 (振る舞いの実装)
    def confirm(self):
        if self.status == BookingStatus.CANCELLED:
            raise ValueError("Cannot confirm a cancelled booking")
        self.status = BookingStatus.CONFIRMED

    # ドメインメソッド: キャンセル
    def cancel(self):
        self.status = BookingStatus.CANCELLED
```

### 3.2 Adapter Layer: DynamoDB Repository
`services/flight/adapters/dynamodb_repository.py` を作成します。
ドメインオブジェクト(`Booking`)をDynamoDBのアイテム形式に変換して保存します。

```python
import os
import boto3
from services.flight.domain.booking import Booking

class DynamoDBRepository:
    def __init__(self, table_name: str = None):
        self.table_name = table_name or os.getenv("TABLE_NAME")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def save(self, booking: Booking) -> None:
        item = {
            "PK": f"TRIP#{booking.trip_id}",
            "SK": f"FLIGHT#{booking.booking_id.value}",
            "type": "FLIGHT",
            "booking_id": booking.booking_id.value,
            "flight_number": booking.flight_number,
            "departure_time": booking.departure_time,
            "arrival_time": booking.arrival_time,
            "price": str(booking.price), # Decimal対応のため文字列化
            "status": booking.status.value,
        }
        self.table.put_item(Item=item)
```

### 3.3 Application Layer: 予約ユースケース
`services/flight/applications/reserve_flight.py` を作成します。
アプリケーションサービスは、ドメインオブジェクトの生成とリポジトリへの保存を調整（オーケストレーション）します。
ここでは `TypedDict` を使用して入力データの構造を明確にします。

```python
from typing import TypedDict
from decimal import Decimal
from services.flight.domain.booking import Booking, BookingID
from services.flight.adapters.dynamodb_repository import DynamoDBRepository

# 入力データの構造定義
class FlightDetails(TypedDict):
    flight_number: str
    departure_time: str
    arrival_time: str
    price: Decimal

class ReserveFlightService:
    def __init__(self, repository: DynamoDBRepository):
        self.repository = repository

    def reserve(self, trip_id: str, flight_details: FlightDetails) -> dict:
        # 1. IDの生成 (冪等性担保のため trip_id から決定論的に生成)
        # 同じ trip_id でのリクエストは常に同じ booking_id になる
        booking_id_value = f"flight_for_{trip_id}"

        # 2. Entityの生成
        booking = Booking(
            booking_id=BookingID(value=booking_id_value),
            trip_id=trip_id,
            flight_number=flight_details["flight_number"],
            departure_time=flight_details["departure_time"],
            arrival_time=flight_details["arrival_time"],
            price=flight_details["price"]
        )

        # 3. ドメインロジックの実行 (必要であれば)
        # booking.validate_flight_schedule() など

        # 4. 永続化
        self.repository.save(booking)

        # 5. 結果の返却 (DTOへの変換推奨だが今回は簡易化)
        return booking.model_dump(mode="json")
```

### 3.4 Handler Layer: Lambda Entrypoint
`services/flight/handlers/reserve.py` を作成します。
外部からの入力を受け取り、アプリケーションサービスを呼び出します。

```python
from decimal import Decimal
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from services.flight.applications.reserve_flight import ReserveFlightService
from services.flight.adapters.dynamodb_repository import DynamoDBRepository

logger = Logger()
tracer = Tracer()

# Global scope initialization (Cold Start execution)
# Lambda のコールドスタート時に一度だけ実行され、接続が再利用されます
repository = DynamoDBRepository()
service = ReserveFlightService(repository)

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logger.info("Received reserve flight request", extra={"event": event})

    try:
        # Step Functions からの入力 or API Gateway からの入力に対応
        # ここでは単純化のため直接 event を参照
        trip_id = event.get("trip_id")
        
        # 入力データを TypedDict の構造に合わせて準備 (Decimal変換など)
        raw_flight_details = event.get("flight_details", {})
        flight_details = {
            "flight_number": raw_flight_details.get("flight_number"),
            "departure_time": raw_flight_details.get("departure_time"),
            "arrival_time": raw_flight_details.get("arrival_time"),
            "price": Decimal(str(raw_flight_details.get("price", "0")))
        }

        # Global instance is used
        result = service.reserve(trip_id, flight_details)
        
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.exception("Failed to reserve flight")
        raise
```

## 4. 単体テストの実装 (Unit Testing)

デプロイ前にロジックを検証するため、テストを作成します。

### 4.1 テストファイルの配置
`tests/unit/services/flight/` ディレクトリを作成します。

### 4.2 テストコードの作成 (`test_reserve_flight.py`)
`mock` ライブラリを使用して DynamoDB への依存をモック化し、Application Service のロジックが正しく動作するか（正常系、異常系）をテストします。

```bash
# テストの実行
pytest tests/unit/services/flight/
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

        # DynamoDB への書き込み権限を付与
        table.grant_write_data(self.flight_reserve)
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