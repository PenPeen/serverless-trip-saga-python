# Hands-on 02: データ永続化層の実装 (DynamoDB)
## 目的
* Single Table Design の理解と実装

## DynamoDB テーブル設計
* **PK**: `TRIP#<uuid>`
* **SK**:
    * `METADATA`: 旅行全体の管理情報（ステータス、作成日等）。1旅行につき1つ。IDは不要。
    * `FLIGHT#<id>`: フライト予約詳細。往復や乗り継ぎ等で複数存在しうるためIDを含む。
    * `HOTEL#<id>`: ホテル予約詳細。複数宿泊等で複数存在しうるためIDを含む。
    * `PAYMENT#<id>`: 決済トランザクション履歴。再試行や分割決済等を考慮しIDを含む。
* **LSI**: 追加不要
* **GSI**: 検索用 (Status, Date等)。**Hands-on 08 で参照用APIの実装時に追加します**。現時点では実装不要。

## アーキテクチャに関する注記 (重要)
* **Microservices vs Monolith**: 本来のマイクロサービスでは「Database per Service (サービスごとにDBを分離する)」が原則です。
* **本ハンズオンの方針**: 今回は学習コストとインフラ管理の簡略化、およびトランザクション集約の学習のため、**Single Table Design** を採用します。本番環境でこのパターンを適用する場合、各サービスのアクセス権限(IAM)を厳密に制御するか、サービスごとにテーブルを物理的に分割することを検討してください。

## CDK実装
* `dynamodb.Table` を定義。Partition Key=`PK`, Sort Key=`SK`。
* `billing_mode=PAY_PER_REQUEST`
* **Construct パターン**を採用し、リソースをモジュール化します。

### ファイル構成
```
infra/
├── constructs/
│   ├── __init__.py
│   └── database.py      # DynamoDB Construct
serverless_trip_saga_stack.py  # メインStack
```

### サンプルコード

#### 1. infra/constructs/database.py
```python
from aws_cdk import (
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class Database(Construct):
    """DynamoDB テーブルを管理する Construct"""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        # DynamoDB Table Definition
        self.table = dynamodb.Table(
            self, "TripTable",
            partition_key=dynamodb.Attribute(
                name="PK",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # 開発環境用: スタック削除時にテーブルも削除する設定
            # 本番環境では RETAIN (デフォルト) を推奨
            removal_policy=RemovalPolicy.DESTROY
        )
```

#### 2. infra/constructs/\_\_init\_\_.py
```python
from .database import Database as Database
```

#### 3. serverless_trip_saga_stack.py
```python
from aws_cdk import Stack
from constructs import Construct
from infra.constructs import Database


class ServerlessTripSagaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Database Construct
        database = Database(self, "Database")

        # 他の Construct から参照する場合: database.table
```

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/dynamodb-design`
*   **コミットメッセージ**: `DynamoDBテーブルの定義`
