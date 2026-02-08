# Hands-on 08: API Gateway Integration & Query Service

## 目的
* 外部アクセスのための REST API 構築（書き込み & 参照）
* Step Functions への Service Integration によるコマンド実行 (Command)
* DynamoDB GSI を活用した参照系サービスの構築 (Query)

## 1. アーキテクチャ概説

書き込み（予約作成）と読み取り（予約参照）で異なる統合パターンを使用します。

* **Command (予約作成)**: `API Gateway -> Step Functions (非同期)`
* **Query (予約参照)**: `API Gateway -> Lambda -> DynamoDB (同期)`

```
Client
  │
  ├── POST /trips ──────> API Gateway ──(AwsIntegration)──> Step Functions
  │                                                            ├── Flight Lambda
  │                                                            ├── Hotel Lambda
  │                                                            └── Payment Lambda
  │
  ├── GET /trips/{id} ──> API Gateway ──(LambdaIntegration)──> get_trip Lambda ──> DynamoDB (Query)
  │
  └── GET /trips ───────> API Gateway ──(LambdaIntegration)──> list_trips Lambda ──> DynamoDB (GSI1 Query)
```

### なぜ書き込みと読み取りで統合パターンが異なるのか

* **書き込み（POST /trips）**: 予約処理は複数サービスをまたぐ分散トランザクション（Saga）であり、Step Functions で非同期実行される。Lambda を経由せず API Gateway から直接 Step Functions を呼び出す **Service Integration** パターンにより、不要な Lambda を排除しコストとレイテンシを削減する。
* **読み取り（GET）**: 単純な DynamoDB の読み取りなので、Lambda で直接クエリを実行する。書き込み側の DDD レイヤー構造は不要であり、シンプルなハンドラーとして実装する。

## 2. DynamoDB GSI の追加 (参照要件への対応)

予約一覧の取得機能を実現するため、保留にしていた GSI を追加します。

### infra/constructs/database.py (更新)

`Database` Construct に Global Secondary Index (GSI) を追加します。

*   **Index Name**: `GSI1`
*   **Partition Key**: `GSI1PK` (String) - 固定値 `TRIPS`（全予約を同一パーティションに集約）
*   **Sort Key**: `GSI1SK` (String) - 例: `TRIP#<trip_id>`

```python
from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class Database(Construct):
    """DynamoDB Construct"""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        self.table = dynamodb.Table(
            self,
            "TripTable",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI の追加 (参照用)
        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.STRING
            ),
        )
```

> **Note**: GSI を追加しただけでは、既存アイテムに `GSI1PK` / `GSI1SK` 属性は付与されません。
> `list_trips` が結果を返すためには、各サービスの Repository でアイテム保存時に GSI 属性を書き込む必要があります。
> 次のセクションで対応します。

### 各 Repository に GSI 属性を追加

GSI にアイテムを投影するため、各サービスの Repository の `save` メソッドで保存する `item` に
`GSI1PK` と `GSI1SK` を追加します。

#### src/services/flight/infrastructure/dynamodb_booking_repository.py (更新)

`save` メソッドの `item` に以下の2行を追加します。

```python
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
            "GSI1PK": "TRIPS",                       # 追加
            "GSI1SK": f"TRIP#{booking.trip_id}",      # 追加
        }
```

#### src/services/hotel/infrastructure/dynamodb_hotel_booking_repository.py (更新)

```python
        item = {
            "PK": f"TRIP#{booking.trip_id}",
            "SK": f"HOTEL#{booking.id}",
            "entity_type": "HOTEL",
            "booking_id": str(booking.id),
            "trip_id": str(booking.trip_id),
            "hotel_name": str(booking.hotel_name),
            "check_in_date": booking.stay_period.check_in,
            "check_out_date": booking.stay_period.check_out,
            "price_amount": str(booking.price.amount),
            "price_currency": str(booking.price.currency),
            "status": booking.status.value,
            "GSI1PK": "TRIPS",                       # 追加
            "GSI1SK": f"TRIP#{booking.trip_id}",      # 追加
        }
```

#### src/services/payment/infrastructure/dynamodb_payment_repository.py (更新)

```python
        item = {
            "PK": f"TRIP#{payment.trip_id}",
            "SK": f"PAYMENT#{payment.id}",
            "entity_type": "PAYMENT",
            "payment_id": str(payment.id),
            "trip_id": str(payment.trip_id),
            "amount": str(payment.amount.amount),
            "currency": str(payment.amount.currency),
            "status": payment.status.value,
            "GSI1PK": "TRIPS",                       # 追加
            "GSI1SK": f"TRIP#{payment.trip_id}",      # 追加
        }
```

> **Note**: 3つの Repository すべてに同じ `GSI1PK` / `GSI1SK` を追加しています。
> 1つの `trip_id` に対して FLIGHT・HOTEL・PAYMENT の3アイテムが GSI に投影されるため、
> `list_trips` Lambda 側で `trip_id` による重複排除を行います。

## 3. Query Service (参照系) の実装

### 3.1 ファイル構成

Query Service は**読み取り専用**のため、Command 側（Flight / Hotel / Payment）のような DDD レイヤー構造は不要です。
シンプルなハンドラーとして実装します。

```
src/services/trip/
├── __init__.py
└── handlers/
    ├── __init__.py
    ├── get_trip.py     # 予約詳細取得（メインテーブル Query）
    └── list_trips.py   # 予約一覧取得（GSI Query）
```

### 3.2 get_trip.py (詳細取得)

`src/services/trip/handlers/get_trip.py`

パスパラメータ `trip_id` を受け取り、DynamoDB を `PK = TRIP#<trip_id>` で Query して
関連する全アイテム（`FLIGHT`, `HOTEL`, `PAYMENT`）を取得・結合して返します。

既存のハンドラーは Step Functions からのイベントを `@event_parser` で処理していますが、
Query Lambda は **API Gateway Lambda Proxy Integration** からのイベントを受け取るため、
Powertools の `@event_source` デコレータで `APIGatewayProxyEvent` として処理します。

```python
import json
import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEvent,
    event_source,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()

TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


@logger.inject_lambda_context
@event_source(data_class=APIGatewayProxyEvent)
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext) -> dict:
    """予約詳細取得 Lambda ハンドラ

    API Gateway Lambda Proxy Integration からのイベントを受け取り、
    DynamoDB をメインテーブルの PK で Query して旅行の全情報を返す。
    """
    path_params = event.path_parameters or {}
    trip_id = path_params.get("trip_id")

    if not trip_id:
        return _response(400, {"message": "trip_id is required"})

    logger.info("Fetching trip details", extra={"trip_id": trip_id})

    try:
        response = table.query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"TRIP#{trip_id}"},
        )

        items = response.get("Items", [])
        if not items:
            return _response(404, {"message": f"Trip not found: {trip_id}"})

        trip = _assemble_trip(trip_id, items)
        return _response(200, trip)

    except Exception:
        logger.exception("Failed to fetch trip details")
        return _response(500, {"message": "Internal server error"})


def _assemble_trip(trip_id: str, items: list[dict]) -> dict:
    """DynamoDB の複数アイテムを1つの旅行レスポンスに結合する

    Single Table Design では1つの PK に対して複数の entity_type のアイテムが存在する。
    entity_type を判別して適切なキーに振り分ける。
    """
    trip: dict = {"trip_id": trip_id}

    for item in items:
        entity_type = item.get("entity_type")

        if entity_type == "FLIGHT":
            trip["flight"] = {
                "booking_id": item["booking_id"],
                "flight_number": item["flight_number"],
                "departure_time": item["departure_time"],
                "arrival_time": item["arrival_time"],
                "price_amount": item["price_amount"],
                "price_currency": item["price_currency"],
                "status": item["status"],
            }
        elif entity_type == "HOTEL":
            trip["hotel"] = {
                "booking_id": item["booking_id"],
                "hotel_name": item["hotel_name"],
                "check_in_date": item["check_in_date"],
                "check_out_date": item["check_out_date"],
                "price_amount": item["price_amount"],
                "price_currency": item["price_currency"],
                "status": item["status"],
            }
        elif entity_type == "PAYMENT":
            trip["payment"] = {
                "payment_id": item["payment_id"],
                "amount": item["amount"],
                "currency": item["currency"],
                "status": item["status"],
            }

    return trip


def _response(status_code: int, body: dict) -> dict:
    """API Gateway Lambda Proxy Integration のレスポンス形式を生成する"""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
```

##### なぜ `json.dumps(body, default=str)` を使うのか

DynamoDB は数値型を Python の `Decimal` として返します。
`json.dumps` は `Decimal` をシリアライズできないため、`default=str` で文字列に変換します。
本プロジェクトでは金額を文字列で保存しているため通常は問題になりませんが、
将来の変更に備えた防御的なコーディングです。

### 3.3 list_trips.py (一覧取得)

`src/services/trip/handlers/list_trips.py`

`GSI1` を使って `GSI1PK = "TRIPS"` で Query し、全予約の一覧を返します。
1つの `trip_id` に対して FLIGHT・HOTEL・PAYMENT の3アイテムが GSI に存在するため、
`trip_id` で重複排除してから返却します。

```python
import json
import os

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEvent,
    event_source,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()

TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


@logger.inject_lambda_context
@event_source(data_class=APIGatewayProxyEvent)
def lambda_handler(event: APIGatewayProxyEvent, context: LambdaContext) -> dict:
    """予約一覧取得 Lambda ハンドラ

    API Gateway Lambda Proxy Integration からのイベントを受け取り、
    DynamoDB の GSI1 を使って全予約の一覧を返す。
    """
    logger.info("Listing all trips")

    try:
        response = table.query(
            IndexName="GSI1",
            KeyConditionExpression="GSI1PK = :pk",
            ExpressionAttributeValues={":pk": "TRIPS"},
        )

        items = response.get("Items", [])
        trips = _deduplicate_trips(items)
        return _response(200, {"trips": trips, "count": len(trips)})

    except Exception:
        logger.exception("Failed to list trips")
        return _response(500, {"message": "Internal server error"})


def _deduplicate_trips(items: list[dict]) -> list[dict]:
    """GSI から取得したアイテムを trip_id で重複排除する

    1つの trip_id に対して FLIGHT・HOTEL・PAYMENT の3アイテムが存在するため、
    trip_id の重複を排除して一覧を返す。
    各サービスの詳細ステータスは GET /trips/{trip_id} で確認する。
    """
    seen: set[str] = set()
    trips: list[dict] = []

    for item in items:
        trip_id = item.get("trip_id", "")
        if trip_id and trip_id not in seen:
            seen.add(trip_id)
            trips.append({"trip_id": trip_id})

    return trips


def _response(status_code: int, body: dict) -> dict:
    """API Gateway Lambda Proxy Integration のレスポンス形式を生成する"""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
```

## 4. API Gateway の構築

### ファイル構成

```
infra/
├── constructs/
│   ├── __init__.py
│   ├── database.py      # Hands-on 02 で作成、GSI 追加済み
│   ├── layers.py        # Hands-on 03 で作成済み
│   ├── functions.py     # Hands-on 04, 05 で作成済み（今回 Query Lambda を追加）
│   ├── orchestration.py # Hands-on 06, 07 で作成済み
│   └── api.py           # API Gateway Construct（今回追加）
```

### 4.1 Functions Construct に Query Lambda を追加

`infra/constructs/functions.py` (更新)

既存の `_create_function` ヘルパーを活用して Query Lambda を追加します。
Command 側の Lambda には読み書き権限 (`grant_read_write_data`) を付与していますが、
Query Lambda には**読み取り権限のみ** (`grant_read_data`) を付与します（最小権限の原則）。

```python
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
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

        # ====================================================================
        # Command 側 Lambda（既存）
        # ====================================================================
        self.flight_reserve = self._create_function(
            "FlightReserveLambda",
            "services.flight.handlers.reserve.lambda_handler",
            "flight-service",
            table,
            common_layer,
        )

        self.flight_cancel = self._create_function(
            "FlightCancelLambda",
            "services.flight.handlers.cancel.lambda_handler",
            "flight-service",
            table,
            common_layer,
        )

        self.hotel_reserve = self._create_function(
            "HotelReserveLambda",
            "services.hotel.handlers.reserve.lambda_handler",
            "hotel-service",
            table,
            common_layer,
        )

        self.hotel_cancel = self._create_function(
            "HotelCancelLambda",
            "services.hotel.handlers.cancel.lambda_handler",
            "hotel-service",
            table,
            common_layer,
        )

        self.payment_process = self._create_function(
            "PaymentProcessLambda",
            "services.payment.handlers.process.lambda_handler",
            "payment-service",
            table,
            common_layer,
        )

        self.payment_refund = self._create_function(
            "PaymentRefundLambda",
            "services.payment.handlers.refund.lambda_handler",
            "payment-service",
            table,
            common_layer,
        )

        # Command 側: 読み書き権限
        for fn in [
            self.flight_reserve,
            self.flight_cancel,
            self.hotel_reserve,
            self.hotel_cancel,
            self.payment_process,
            self.payment_refund,
        ]:
            table.grant_read_write_data(fn)

        # ====================================================================
        # Query 側 Lambda（今回追加）
        # ====================================================================
        self.get_trip = self._create_function(
            "GetTripLambda",
            "services.trip.handlers.get_trip.lambda_handler",
            "trip-service",
            table,
            common_layer,
        )

        self.list_trips = self._create_function(
            "ListTripsLambda",
            "services.trip.handlers.list_trips.lambda_handler",
            "trip-service",
            table,
            common_layer,
        )

        # Query 側: 読み取り権限のみ（最小権限の原則）
        table.grant_read_data(self.get_trip)
        table.grant_read_data(self.list_trips)

    def _create_function(
        self,
        id: str,
        handler: str,
        service_name: str,
        table: dynamodb.Table,
        common_layer: _lambda.LayerVersion,
    ) -> _lambda.Function:
        return _lambda.Function(
            self,
            id,
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler=handler,
            code=_lambda.Code.from_asset("src"),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": service_name,
            },
        )
```

### 4.2 API Gateway Construct の作成

`infra/constructs/api.py` (新規作成)

```python
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_stepfunctions as sfn
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

        # REST API 定義
        self.rest_api = apigateway.RestApi(
            self,
            "TripApi",
            rest_api_name="Trip Booking API",
            deploy_options=apigateway.StageOptions(
                metrics_enabled=True,
                throttling_rate_limit=100,
                throttling_burst_limit=200,
            ),
        )

        # Step Functions 実行用 IAM Role
        sfn_role = iam.Role(
            self,
            "ApiGatewayStepFunctionsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        state_machine.grant_start_execution(sfn_role)

        # リソース定義
        trips_resource = self.rest_api.root.add_resource("trips")
        trip_resource = trips_resource.add_resource("{trip_id}")

        # ====================================================================
        # POST /trips -> Step Functions (非同期)
        # ====================================================================
        trips_resource.add_method(
            "POST",
            apigateway.AwsIntegration(
                service="states",
                action="StartExecution",
                options=apigateway.IntegrationOptions(
                    credentials_role=sfn_role,
                    request_templates={
                        "application/json": (
                            '{"stateMachineArn": "'
                            + state_machine.state_machine_arn
                            + '", "input": "$util.escapeJavaScript($input.body)"}'
                        )
                    },
                    integration_responses=[
                        apigateway.IntegrationResponse(status_code="200"),
                        apigateway.IntegrationResponse(
                            status_code="400",
                            selection_pattern="4\\d{2}",
                        ),
                        apigateway.IntegrationResponse(
                            status_code="500",
                            selection_pattern="5\\d{2}",
                        ),
                    ],
                ),
            ),
            method_responses=[
                apigateway.MethodResponse(status_code="200"),
                apigateway.MethodResponse(status_code="400"),
                apigateway.MethodResponse(status_code="500"),
            ],
        )

        # ====================================================================
        # GET /trips -> Lambda (list_trips)
        # ====================================================================
        trips_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(list_trips),
        )

        # ====================================================================
        # GET /trips/{trip_id} -> Lambda (get_trip)
        # ====================================================================
        trip_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(get_trip),
        )
```

### 4.3 infra/constructs/\_\_init\_\_.py (更新)

```python
from .api import Api as Api
from .database import Database as Database
from .functions import Functions as Functions
from .layers import Layers as Layers
from .orchestration import Orchestration as Orchestration
```

### 4.4 serverless_trip_saga_stack.py (更新)

```python
from aws_cdk import Stack
from constructs import Construct

from infra.constructs import Api, Database, Functions, Layers, Orchestration


class ServerlessTripSagaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Database Construct
        database = Database(self, "Database")

        # Layers Construct
        layers = Layers(self, "Layers")

        # Functions Construct
        fns = Functions(
            self,
            "Functions",
            table=database.table,
            common_layer=layers.common_layer,
        )

        # Orchestration Construct
        orchestration = Orchestration(self, "Orchestration", functions=fns)

        # API Gateway Construct
        Api(
            self,
            "Api",
            state_machine=orchestration.state_machine,
            get_trip=fns.get_trip,
            list_trips=fns.list_trips,
        )
```

> **Note**: `Orchestration` の呼び出し方は Hands-on 07 と同じです。
> 変更点は戻り値を `orchestration` 変数に格納して `state_machine` を `Api` に渡している点のみです。

## 5. エンドポイント一覧

| Method | Resource | Integration | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/trips` | **Step Functions** (`StartExecution`) | 予約プロセスの開始 (非同期) |
| `GET` | `/trips/{trip_id}` | **Lambda** (`get_trip`) | 予約詳細の取得 |
| `GET` | `/trips` | **Lambda** (`list_trips`) | 全予約の一覧取得 |

## 6. Step Functions Integration (POST /trips) の詳細

### AwsIntegration

Step Functions の `StartExecution` アクションを API Gateway から直接呼び出します。
Lambda を経由しないため、コールドスタートの影響を受けず、コストも削減されます。

### VTL (Velocity Template Language) によるリクエスト変換

クライアントからの JSON ボディは文字列としてエスケープし、Step Functions の `input` パラメータに渡す必要があります。

```python
# request_templates の VTL テンプレートが生成するリクエスト:
# {
#   "stateMachineArn": "arn:aws:states:ap-northeast-1:123456789012:stateMachine:...",
#   "input": "{\"trip_id\": \"abc-123\", \"flight_details\": {...}}"
# }
#
# $util.escapeJavaScript($input.body) により、
# クライアントの JSON ボディがエスケープされた文字列として渡される。
```

### エラーハンドリング (integration_responses / method_responses)

`StartExecution` API 自体が失敗した場合（IAM 権限不足、無効な入力など）に備え、
`integration_responses` で `selection_pattern` を使って HTTP ステータスコードをマッピングしています。

* `4\\d{2}` — クライアントエラー（400系）をキャッチし `400` として返却
* `5\\d{2}` — サーバーエラー（500系）をキャッチし `500` として返却

`method_responses` にも対応するステータスコードを定義しないと、API Gateway がレスポンスを返せません。

### deploy_options (メトリクス・スロットリング)

`RestApi` の `deploy_options` で運用に必要な設定を行っています。

* `metrics_enabled=True` — CloudWatch メトリクス（4XX/5XX エラー率、レイテンシ等）を有効化
* `throttling_rate_limit` / `throttling_burst_limit` — API のレート制限を設定し、過負荷やコスト暴走を防止

> **Note**: 本番環境ではさらに `logging_level=apigateway.MethodLoggingLevel.INFO` を設定して
> 実行ログを有効化することを推奨します。ただし、これには**アカウントレベルで API Gateway 用の
> CloudWatch Logs IAM ロール**が事前に設定されている必要があります（`apigateway.CfnAccount`）。
> 未設定の場合、デプロイ時にエラーとなるため、本ハンズオンでは省略しています。

### IAM Role

`grant_start_execution()` により、API Gateway が Step Functions の `StartExecution` を呼び出す権限を自動付与します。

### 非同期 API の挙動 (Asynchronous Pattern)

Step Functions への連携は**非同期**で行われます。

1. クライアントが `POST /trips` をコール
2. API Gateway が `200 OK` と `executionArn`（実行ID）を即座に返却
3. Step Functions がバックグラウンドで Saga ワークフローを実行
4. クライアントは `GET /trips/{trip_id}` をポーリングして結果を確認

> **Note**: API のレスポンス時点では「予約確約」ではありません（Eventual Consistency）。
> 実際の予約結果を知るには、`GET /trips/{trip_id}` で各サービスのステータスを確認します。

## 7. デプロイと動作確認

```bash
cdk deploy
```

### 7.1 予約作成 (POST /trips)

```bash
# API Gateway の URL を取得（cdk deploy の出力から）
API_URL="https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/prod"

# 予約リクエスト
curl -X POST "${API_URL}/trips" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "trip-test-001",
    "flight_details": {
      "flight_number": "NH001",
      "departure_time": "2025-03-01T10:00:00",
      "arrival_time": "2025-03-01T12:00:00",
      "price_amount": 50000,
      "price_currency": "JPY"
    },
    "hotel_details": {
      "hotel_name": "Tokyo Hotel",
      "check_in_date": "2025-03-01",
      "check_out_date": "2025-03-03",
      "price_amount": 30000,
      "price_currency": "JPY"
    },
    "amount": 80000,
    "currency": "JPY"
  }'

# レスポンス例:
# {"executionArn":"arn:aws:states:...","startDate":1234567890.123}
```

### 7.2 予約詳細取得 (GET /trips/{trip_id})

Step Functions の実行完了後（数秒待ってから）：

```bash
curl "${API_URL}/trips/trip-test-001"

# レスポンス例:
# {
#   "trip_id": "trip-test-001",
#   "flight": {
#     "booking_id": "flight_for_trip-test-001",
#     "flight_number": "NH001",
#     "status": "PENDING"
#   },
#   "hotel": { ... },
#   "payment": { ... }
# }
```

### 7.3 予約一覧取得 (GET /trips)

```bash
curl "${API_URL}/trips"

# レスポンス例:
# {
#   "trips": [
#     {"trip_id": "trip-test-001"}
#   ],
#   "count": 1
# }
```

## 8. 次のステップ

API Gateway と Query Service の実装が完了し、外部からシステムを利用できるようになりました。
次は CI/CD パイプラインを構築し、安全なデプロイフローを実現します。

👉 **[Hands-on 09: CI/CD with CodePipeline](./09-cicd-codepipeline.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/api-gateway-query`
*   **コミットメッセージ**: `API Gatewayと参照系サービスの実装`
