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

### CDK実装 (`serverless_trip_saga_python_stack.py`)
`TripTable` に Global Secondary Index (GSI) を追加します。

*   **Index Name**: `GSI1`
*   **Partition Key**: `GSI1PK` (String) - 例: `USER#<user_id>`
*   **Sort Key**: `GSI1SK` (String) - 例: `DATE#<iso_timestamp>`

```python
        # GSIの追加
        table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(name="GSI1PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="GSI1SK", type=dynamodb.AttributeType.STRING),
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

### 4.1 RestApi の定義とIAM権限
CDK で `apigateway.RestApi` を定義します。Step Functions を呼び出すための IAM Role も設定します。

### 4.2 リソースとメソッドの定義

| Method | Resource | Integration | Auth | Description |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/trips` | **Step Functions** (`StartExecution`) | IAM / Cog | 予約プロセスの開始 (非同期) |
| `GET` | `/trips/{trip_id}` | **Lambda** (`get_trip`) | IAM / Cog | 予約詳細の取得 |
| `GET` | `/trips` | **Lambda** (`list_trips`) | IAM / Cog | 自分の予約一覧取得 |

### 4.3 Step Functions Integration (POST /trips) の詳細
* **AwsIntegration**: Step Functions の `StartExecution` アクションを API Gateway から直接呼び出します。
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