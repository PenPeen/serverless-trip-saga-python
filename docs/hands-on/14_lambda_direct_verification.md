# Hands-on 14: クエリ Lambda 単体検証（GetTrip / ListTrips）

本セクションでは、Step Functions オーケストレーションに含まれない**クエリ Lambda（`GetTripLambda`, `ListTripsLambda`）を `aws lambda invoke` で直接実行**し、入出力を単体で検証します。

クエリ Lambda は API Gateway HTTP API v2 経由でリクエストを受け取る設計のため、ここでは API Gateway イベント形式を模擬して直接呼び出します。

## 目的

1. **旅行詳細取得 Lambda の単体実行**: API Gateway HTTP API v2 イベント形式を模擬し、特定の `trip_id` のデータを取得できることを確認する。
2. **旅行一覧取得 Lambda の単体実行**: GSI を利用した全旅行一覧取得ができることを確認する。
3. **404 ハンドリングの確認**: 存在しない `trip_id` に対して適切なエラーレスポンスが返ることを確認する。

## 前提条件

- `cdk deploy` が完了していること。
- `events/lambda/` ディレクトリのイベントファイルが配置されていること。
- AWS CLI v2, `jq` が実行可能であること。
- DynamoDB にテストデータが存在すること（[Hands-on 12](./12_e2e_verification_and_chaos.md) 等で事前に旅行データを作成済みであること）。

## 1. 環境変数の設定

Lambda 関数名は CDK デプロイ時にハッシュ付きで生成されるため、AWS CLI で動的に取得します。

```bash
# クエリ Lambda 関数名の取得
export GET_TRIP_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'GetTrip')].FunctionName | [0]" \
    --output text)

export LIST_TRIPS_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'ListTrips')].FunctionName | [0]" \
    --output text)

# DynamoDB テーブル名
export BOOKING_TABLE_NAME=$(aws dynamodb list-tables \
    --query "TableNames[?contains(@, 'TripTable')] | [0]" \
    --output text)

# 確認
echo "GetTrip   : $GET_TRIP_FN"
echo "ListTrips : $LIST_TRIPS_FN"
echo "Table     : $BOOKING_TABLE_NAME"
```

## 2. クエリ Lambda の直接実行

クエリ Lambda (`GetTripLambda`, `ListTripsLambda`) は `@event_source(data_class=APIGatewayProxyEventV2)` デコレータを使用するため、**API Gateway HTTP API v2 形式のイベント**を渡す必要があります。`events/lambda/` にテスト用イベントファイルを用意しています。

> **レスポンス形式**: クエリ Lambda は `{"statusCode": 200, "headers": {...}, "body": "{...}"}` 形式で返します。`jq '.body | fromjson'` でボディを展開して確認します。

### 2.1 旅行詳細取得 Lambda (`GetTripLambda`)

DynamoDB に存在する `trip_id` の詳細を取得します。

**イベントファイル**: `events/lambda/get_trip.json`（`pathParameters.trip_id` が設定済み）

```bash
aws lambda invoke \
    --function-name $GET_TRIP_FN \
    --payload file://events/lambda/get_trip.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq '{statusCode, body: (.body | fromjson)}'
```

**期待レスポンス**:
```json
{
  "statusCode": 200,
  "body": {
    "trip_id": "trip-lambda-001",
    "flight": {
      "booking_id": "flight_for_trip-lambda-001",
      "flight_number": "NH001",
      ...
    },
    "hotel": { ... },
    "payment": { ... }
  }
}
```

**trip_id を動的に変更してクエリする場合**:
```bash
TRIP_ID="trip-lambda-001"
jq --arg tid "$TRIP_ID" \
    '.pathParameters.trip_id = $tid | .rawPath = "/trips/\($tid)" | .requestContext.http.path = "/trips/\($tid)"' \
    events/lambda/get_trip.json > /tmp/get_trip_custom.json

aws lambda invoke \
    --function-name $GET_TRIP_FN \
    --payload file:///tmp/get_trip_custom.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && cat /tmp/response.json | jq '{statusCode, body: (.body | fromjson)}'
```

**存在しない trip_id の場合 (404 確認)**:
```bash
jq '.pathParameters.trip_id = "trip-not-exist" | .rawPath = "/trips/trip-not-exist" | .requestContext.http.path = "/trips/trip-not-exist"' \
    events/lambda/get_trip.json > /tmp/get_trip_404.json

aws lambda invoke \
    --function-name $GET_TRIP_FN \
    --payload file:///tmp/get_trip_404.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && cat /tmp/response.json | jq '{statusCode, body: (.body | fromjson)}'
```

> **期待値**: `{"statusCode": 404, "body": {"message": "Trip not found: trip-not-exist"}}`

### 2.2 旅行一覧取得 Lambda (`ListTripsLambda`)

**イベントファイル**: `events/lambda/list_trips.json`

```bash
aws lambda invoke \
    --function-name $LIST_TRIPS_FN \
    --payload file://events/lambda/list_trips.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq '{statusCode, body: (.body | fromjson)}'
```

**期待レスポンス**:
```json
{
  "statusCode": 200,
  "body": {
    "trips": [
      {"trip_id": "trip-lambda-001"},
      ...
    ],
    "count": 1
  }
}
```

> **ポイント**: DynamoDB の GSI1 (`TRIPS`) を使ったクエリで全旅行を一覧取得します。同一 `trip_id` に対して FLIGHT / HOTEL / PAYMENT の 3 レコードが存在しますが、`trip_id` で重複排除されて返却されます。

## 3. まとめ

| Lambda 関数 | イベントファイル | 入力スキーマ | 検証ポイント |
|---|---|---|---|
| GetTripLambda | `get_trip.json` | API GW V2 Event (`pathParameters.trip_id`) | 集計レスポンス・404 ハンドリング |
| ListTripsLambda | `list_trips.json` | API GW V2 Event | GSI クエリ・重複排除 |

Step Functions を経由した E2E 検証については 👉 **[Hands-on 12: E2E Verification & Chaos Testing](./12_e2e_verification_and_chaos.md)** を参照してください。
