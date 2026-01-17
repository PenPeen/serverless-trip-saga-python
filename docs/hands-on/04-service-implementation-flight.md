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

### 3.1 Domain Layer: フライト予約モデル
`services/flight/domain/booking.py` を作成し、予約データを表現するクラスとバリデーションを定義します (Pydantic利用)。

### 3.2 Adapter Layer: DynamoDB Repository
`services/flight/adapters/dynamodb_repository.py` を作成します。
Hands-on 02 で作成したテーブルに対し、PK=`TRIP#<id>`, SK=`FLIGHT#<id>` の形式でデータを保存する処理を実装します。

### 3.3 Application Layer: 予約ユースケース
`services/flight/applications/reserve_flight.py` を作成します。
入力データを受け取り、ドメインオブジェクトを生成し、リポジトリを通じて保存する一連の流れを記述します。

### 3.4 Handler Layer: Lambda Entrypoint
`services/flight/handlers/reserve.py` を作成します。
Powertools を使用してイベントをパースし、Application Layer を呼び出します。

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
            runtime=_lambda.Runtime.PYTHON_3_12,
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
