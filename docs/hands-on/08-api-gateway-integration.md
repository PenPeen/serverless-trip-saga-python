# Hands-on 08: API Gateway Integration & Query Service
## 目的
* 外部アクセスのための API 構築 (Command & Query)
* Step Functions への Service Integration (Command)
* DynamoDB GSI を活用した参照系サービスの構築 (Query)

## 1. アーキテクチャ概説 (CQRS Lite)
書き込み (Command) と読み取り (Query) の責務を分離します。
* **Command (予約作成)**: API Gateway -> Step Functions (非同期)
* **Query (予約参照)**: API Gateway -> Lambda -> DynamoDB (同期)

## 2. DynamoDB GSI の追加 (参照要件への対応)
検索機能（ユーザーごとの予約履歴取得など）を実現するため、保留にしていた GSI を追加します。

### infra/constructs/database.py (更新)
`Database` Construct に Global Secondary Index (GSI) を追加します。

*   **Index Name**: `GSI1`
*   **Partition Key**: `GSI1PK` (String) - 例: `USER#<user_id>`
*   **Sort Key**: `GSI1SK` (String) - 例: `DATE#<iso_timestamp>`

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
            removal_policy=RemovalPolicy.DESTROY
        )

        # GSI の追加 (参照用)
        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK",
                type=dynamodb.AttributeType.STRING
            ),
        )
```

## 3. Query Service (参照系) の実装

### 3.1 Lambda実装
`services/trip/handlers/` に以下の関数を実装します。

1.  **`get_trip.py` (詳細取得)**:
    *   パスパラメータ `trip_id` を受け取る。
    *   DynamoDB を `PK=TRIP#<trip_id>` で `query` (または `get_item`) する。
    *   関連する全アイテム (`METADATA`, `FLIGHT`, `HOTEL`, `PAYMENT`) を取得して結合し、JSONで返す。

2.  **`list_trips.py` (一覧取得)**:
    *   クエリパラメータ `user_id` を受け取る。
    *   DynamoDB を `GSI1` を使って `query` する (`KeyConditionExpression: GSI1PK = USER#<user_id>`)。
    *   `METADATA` のリストを返す。

## 4. API Gateway の構築

### ファイル構成
```
infra/
├── constructs/
│   ├── __init__.py
│   ├── database.py      # Hands-on 02 で作成、GSI追加済み
│   ├── layers.py        # Hands-on 03 で作成済み
│   ├── functions.py     # Hands-on 04, 05 で作成済み (Query Lambda追加)
│   ├── orchestration.py # Hands-on 06, 07 で作成済み
│   └── api.py           # API Gateway Construct (今回追加)
```

### 4.1 Functions Construct に Query Lambda を追加

```python
# infra/constructs/functions.py に追加

        # ========================================================================
        # Trip Query Service Lambda (今回追加)
        # ========================================================================
        self.get_trip = _lambda.Function(
            self, "GetTripLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.trip.handlers.get_trip.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "trip-service",
            },
        )

        self.list_trips = _lambda.Function(
            self, "ListTripsLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.trip.handlers.list_trips.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "trip-service",
            },
        )

        # 読み取り権限を付与
        table.grant_read_data(self.get_trip)
        table.grant_read_data(self.list_trips)
```

### 4.2 API Gateway Construct の作成

#### infra/constructs/api.py
```python
from aws_cdk import (
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
)
from constructs import Construct


class Api(Construct):
    """API Gateway を管理する Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        state_machine: sfn.StateMachine,
        get_trip: _lambda.Function,
        list_trips: _lambda.Function,
    ) -> None:
        super().__init__(scope, id)

        # ========================================================================
        # REST API 定義
        # ========================================================================
        self.rest_api = apigateway.RestApi(
            self, "TripApi",
            rest_api_name="Trip Booking API",
        )

        # ========================================================================
        # Step Functions 実行用 IAM Role
        # ========================================================================
        sfn_role = iam.Role(
            self, "ApiGatewayStepFunctionsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        state_machine.grant_start_execution(sfn_role)

        # ========================================================================
        # リソース定義
        # ========================================================================
        trips_resource = self.rest_api.root.add_resource("trips")
        trip_resource = trips_resource.add_resource("{trip_id}")

        # POST /trips -> Step Functions (非同期)
        trips_resource.add_method(
            "POST",
            apigateway.AwsIntegration(
                service="states",
                action="StartExecution",
                options=apigateway.IntegrationOptions(
                    credentials_role=sfn_role,
                    request_templates={
                        "application/json": f'{{"stateMachineArn": "{state_machine.state_machine_arn}", "input": "$util.escapeJavaScript($input.body)"}}'
                    },
                    integration_responses=[
                        apigateway.IntegrationResponse(status_code="200")
                    ],
                ),
            ),
            method_responses=[apigateway.MethodResponse(status_code="200")],
        )

        # GET /trips -> Lambda (list_trips)
        trips_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(list_trips),
        )

        # GET /trips/{trip_id} -> Lambda (get_trip)
        trip_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_trip),
        )
```

### 4.3 infra/constructs/\_\_init\_\_.py (更新)
```python
from .database import Database
from .layers import Layers
from .functions import Functions
from .orchestration import Orchestration
from .api import Api

__all__ = ["Database", "Layers", "Functions", "Orchestration", "Api"]
```

### 4.4 serverless_trip_saga_stack.py (更新)
```python
from aws_cdk import Stack
from constructs import Construct
from infra.constructs import Database, Layers, Functions, Orchestration, Api


class ServerlessTripSagaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        database = Database(self, "Database")
        layers = Layers(self, "Layers")
        functions = Functions(
            self, "Functions",
            table=database.table,
            common_layer=layers.common_layer,
        )
        orchestration = Orchestration(
            self, "Orchestration",
            flight_reserve=functions.flight_reserve,
            flight_cancel=functions.flight_cancel,
            hotel_reserve=functions.hotel_reserve,
            hotel_cancel=functions.hotel_cancel,
            payment_process=functions.payment_process,
        )

        # API Gateway Construct
        api = Api(
            self, "Api",
            state_machine=orchestration.state_machine,
            get_trip=functions.get_trip,
            list_trips=functions.list_trips,
        )
```

### 4.5 エンドポイント一覧

| Method | Resource | Integration | Auth | Description |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/trips` | **Step Functions** (`StartExecution`) | IAM / Cog | 予約プロセスの開始 (非同期) |
| `GET` | `/trips/{trip_id}` | **Lambda** (`get_trip`) | IAM / Cog | 予約詳細の取得 |
| `GET` | `/trips` | **Lambda** (`list_trips`) | IAM / Cog | 自分の予約一覧取得 |

### 4.6 Step Functions Integration (POST /trips) の詳細
* **AwsIntegration**: Step Functions の `StartExecution` アクションを API Gateway から直接呼び出します。
* **VTL (Velocity Template Language) によるリクエスト変換**:
    * クライアントからの JSON ボディは文字列としてエスケープする必要があります。
    * 以下の `request_templates` 定義により、API Gateway はリクエストボディ全体(`$input.body`)をエスケープし、Step Functions の `input` パラメータとしてラップして渡します。
    
    ```python
    # VTL Template Example
    # {
    #   "stateMachineArn": "arn:aws:states:...",
    #   "input": "{\"trip_id\": \"123\", ...}"  <-- エスケープされたJSON文字列
    # }
    request_templates={
        "application/json": f'{{"stateMachineArn": "{state_machine.state_machine_arn}", "input": "$util.escapeJavaScript($input.body)"}}'
    },
    ```

* **IAM Role**: API Gateway が Step Functions を実行できる権限を付与します。
* **非同期APIの挙動 (Asynchronous Pattern)**:
    * Step Functions への連携は**非同期**で行われます。
    * クライアントには API Gateway から `200 OK` と共に `executionArn` (実行ID) が返却されます。
    * **Note**: APIのレスポンス時点で「予約確約」ではありません（Eventual Consistency）。
    * 実際の予約結果を知るには、今回実装する `GET /trips/{trip_id}` API をクライアントがポーリングし、ステータスが完了になるのを待つ必要があります。

## 5. デプロイと動作確認

```bash
cdk deploy
```

1.  **予約作成**: `POST /trips` をコール -> `executionArn` が返る。
2.  **一覧取得**: `GET /trips?user_id=test_user` -> 予約した旅行が表示されることを確認 (GSI動作確認)。
3.  **詳細取得**: `GET /trips/<uuid>` -> 詳細データが返ることを確認。
4.  **クエリ効率の検証 (重要)**:
    *   DynamoDB のメトリクスまたは `ConsumedCapacity` を確認し、一覧取得 (`list_trips`) がテーブル全体を探索する **Scan** ではなく、インデックスを使用した効率的な **Query** として実行されていることを確認します。

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/api-gateway-query`
*   **コミットメッセージ**: `API Gatewayと参照系サービスの実装`