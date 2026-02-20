# Hands-on 14: Lambda 単体検証 (Step Functions を経由しない直接呼び出し)

本セクションでは、Step Functions オーケストレーションを経由せず、**Lambda 関数を `aws lambda invoke` で直接実行**し、各関数の入出力と DynamoDB への書き込みを単体で検証します。

Step Functions 経由の E2E 検証 ([Hands-on 12](./12_e2e_verification_and_chaos.md)) とは異なり、ここでは各 Lambda の責務を独立して確認することが目的です。

## 目的

1. **Saga Lambda の単体実行**: Reserve / Cancel / Refund 系 Lambda をそれぞれ直接呼び出し、正しく動作することを確認する。
2. **クエリ Lambda の単体実行**: API Gateway HTTP API v2 イベント形式を模擬し、データ取得ができることを確認する。
3. **バリデーションエラーの確認**: 不正な入力に対して Lambda が適切なエラーを返すことを確認する。
4. **補償トランザクション Lambda の単体実行**: キャンセル / 払い戻し Lambda を直接実行し、冪等性を確認する。

## 前提条件

- `cdk deploy` が完了していること。
- `events/lambda/` ディレクトリのイベントファイルが配置されていること。
- AWS CLI v2, `jq` が実行可能であること。

## 1. 環境変数の設定

Lambda 関数名は CDK デプロイ時にハッシュ付きで生成されるため、AWS CLI で動的に取得します。

```bash
# 各 Lambda 関数名の取得
export FLIGHT_RESERVE_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'FlightReserve')].FunctionName | [0]" \
    --output text)

export HOTEL_RESERVE_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'HotelReserve')].FunctionName | [0]" \
    --output text)

export PAYMENT_PROCESS_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'PaymentProcess')].FunctionName | [0]" \
    --output text)

export FLIGHT_CANCEL_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'FlightCancel')].FunctionName | [0]" \
    --output text)

export HOTEL_CANCEL_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'HotelCancel')].FunctionName | [0]" \
    --output text)

export PAYMENT_REFUND_FN=$(aws lambda list-functions \
    --query "Functions[?contains(FunctionName, 'PaymentRefund')].FunctionName | [0]" \
    --output text)

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
echo "FlightReserve  : $FLIGHT_RESERVE_FN"
echo "HotelReserve   : $HOTEL_RESERVE_FN"
echo "PaymentProcess : $PAYMENT_PROCESS_FN"
echo "FlightCancel   : $FLIGHT_CANCEL_FN"
echo "HotelCancel    : $HOTEL_CANCEL_FN"
echo "PaymentRefund  : $PAYMENT_REFUND_FN"
echo "GetTrip        : $GET_TRIP_FN"
echo "ListTrips      : $LIST_TRIPS_FN"
echo "Table          : $BOOKING_TABLE_NAME"
```

## 2. Saga Lambda の個別実行（正常系）

Saga Lambda はハンドラ内で `event.get("Payload", event)` によってペイロードを取り出すため、**Step Functions ラッパーなしでも直接 JSON を渡して実行できます**。

検証に使用する `trip_id`: **`trip-lambda-001`**

> **注意**: `trip-lambda-001` が既に DynamoDB に存在する場合は、`ConditionalCheckFailedException` が発生します。その場合は `trip-lambda-002` など別の `trip_id` に変更してください。

### 2.1 フライト予約 Lambda (`FlightReserveLambda`)

**イベントファイル**: `events/lambda/flight_reserve.json`

```bash
aws lambda invoke \
    --function-name $FLIGHT_RESERVE_FN \
    --payload file://events/lambda/flight_reserve.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq .
```

**期待レスポンス**:
```json
{
  "status": "success",
  "data": {
    "booking_id": "flight_for_trip-lambda-001",
    "trip_id": "trip-lambda-001",
    "flight_number": "NH001",
    "departure_time": "2026-03-01T10:00:00",
    "arrival_time": "2026-03-01T14:00:00",
    "price_amount": "50000",
    "price_currency": "JPY",
    "status": "PENDING"
  }
}
```

> **ポイント**: Step Functions 経由の場合は `CONFIRMED` になりますが、単体実行では Factory の初期値である `PENDING` ステータスになります。

### 2.2 ホテル予約 Lambda (`HotelReserveLambda`)

**イベントファイル**: `events/lambda/hotel_reserve.json`

```bash
aws lambda invoke \
    --function-name $HOTEL_RESERVE_FN \
    --payload file://events/lambda/hotel_reserve.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq .
```

**期待レスポンス**:
```json
{
  "status": "success",
  "data": {
    "booking_id": "hotel_for_trip-lambda-001",
    "trip_id": "trip-lambda-001",
    "hotel_name": "Grand Hotel Tokyo",
    "check_in_date": "2026-03-01",
    "check_out_date": "2026-03-03",
    "nights": 2,
    "price_amount": "30000",
    "price_currency": "JPY",
    "status": "PENDING"
  }
}
```

### 2.3 決済処理 Lambda (`PaymentProcessLambda`)

**イベントファイル**: `events/lambda/payment_process.json`

```bash
aws lambda invoke \
    --function-name $PAYMENT_PROCESS_FN \
    --payload file://events/lambda/payment_process.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq .
```

**期待レスポンス**:
```json
{
  "status": "success",
  "data": {
    "payment_id": "payment_for_trip-lambda-001",
    "trip_id": "trip-lambda-001",
    "amount": "80000",
    "currency": "JPY",
    "status": "PENDING"
  }
}
```

### 2.4 DynamoDB でのデータ確認

3 つの Lambda 実行後、DynamoDB に FLIGHT / HOTEL / PAYMENT の 3 レコードが存在することを確認します。

```bash
aws dynamodb scan \
    --table-name $BOOKING_TABLE_NAME \
    --filter-expression "PK = :pk" \
    --expression-attribute-values '{":pk": {"S": "TRIP#trip-lambda-001"}}' \
    | jq '.Items[] | {SK: .SK.S, status: .status.S}'
```

**期待値**: 3 件のアイテムが返却され、それぞれ `status` が存在すること。

## 3. クエリ Lambda の直接実行

クエリ Lambda (`GetTripLambda`, `ListTripsLambda`) は `@event_source(data_class=APIGatewayProxyEventV2)` デコレータを使用するため、**API Gateway HTTP API v2 形式のイベント**を渡す必要があります。`events/lambda/` にテスト用イベントファイルを用意しています。

> **レスポンス形式の違い**: クエリ Lambda は `{"statusCode": 200, "headers": {...}, "body": "{...}"}` 形式で返します。`jq '.body | fromjson'` でボディを展開して確認します。

### 3.1 旅行詳細取得 Lambda (`GetTripLambda`)

Section 2 で作成した `trip-lambda-001` の詳細を取得します。

**イベントファイル**: `events/lambda/get_trip.json`（`pathParameters.trip_id: "trip-lambda-001"` が設定済み）

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

### 3.2 旅行一覧取得 Lambda (`ListTripsLambda`)

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

## 4. バリデーションエラーの確認

不正な入力を送ると、Lambda が `FunctionError` で終了します（DynamoDB への書き込みは行われません）。

> **確認方法**: `aws lambda invoke` の終了コードは正常でも、レスポンスファイルに `errorMessage` が含まれます。また、`--log-type Tail` オプションでログを取得できます。

### 4.1 フライト予約エラー（フライト番号が空・価格が負）

**イベントファイル**: `events/lambda/flight_reserve_invalid.json`

```bash
aws lambda invoke \
    --function-name $FLIGHT_RESERVE_FN \
    --payload file://events/lambda/flight_reserve_invalid.json \
    --cli-binary-format raw-in-base64-out \
    --log-type Tail \
    /tmp/response.json \
    | jq -r '.LogResult' | base64 -d | tail -5

echo "=== Error Response ===" && cat /tmp/response.json | jq .
```

**期待値**: レスポンスに `ValidationError` のエラーメッセージが含まれること。

### 4.2 ホテル予約エラー（ホテル名が空・日付形式不正）

**イベントファイル**: `events/lambda/hotel_reserve_invalid.json`

```bash
aws lambda invoke \
    --function-name $HOTEL_RESERVE_FN \
    --payload file://events/lambda/hotel_reserve_invalid.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    ; echo "=== Error Response ===" && cat /tmp/response.json | jq .
```

### 4.3 決済エラー（金額が負）

**イベントファイル**: `events/lambda/payment_process_invalid.json`

```bash
aws lambda invoke \
    --function-name $PAYMENT_PROCESS_FN \
    --payload file://events/lambda/payment_process_invalid.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    ; echo "=== Error Response ===" && cat /tmp/response.json | jq .
```

**CloudWatch Logs でのエラー確認**:
```bash
# フライト予約のエラーログ確認 (直近 5 分)
aws logs filter-log-events \
    --log-group-name "/aws/lambda/$FLIGHT_RESERVE_FN" \
    --filter-pattern "ERROR" \
    --start-time $(python3 -c "import time; print(int((time.time() - 300) * 1000))") \
    | jq -r '.events[].message'
```

## 5. 補償トランザクション Lambda の個別実行

Section 2 で作成した `trip-lambda-001` のデータを使用して、キャンセル / 払い戻し Lambda を直接呼び出します。

### 5.1 決済払い戻し Lambda (`PaymentRefundLambda`)

**イベントファイル**: `events/lambda/payment_refund.json`

```bash
aws lambda invoke \
    --function-name $PAYMENT_REFUND_FN \
    --payload file://events/lambda/payment_refund.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq .
```

**期待レスポンス**:
```json
{
  "status": "success",
  "data": {
    "payment_id": "payment_for_trip-lambda-001",
    "trip_id": "trip-lambda-001",
    "amount": "80000",
    "currency": "JPY",
    "status": "REFUNDED"
  }
}
```

### 5.2 ホテルキャンセル Lambda (`HotelCancelLambda`)

**イベントファイル**: `events/lambda/hotel_cancel.json`

```bash
aws lambda invoke \
    --function-name $HOTEL_CANCEL_FN \
    --payload file://events/lambda/hotel_cancel.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq .
```

**期待レスポンス** (`status` の表記は `CANCELED`):
```json
{
  "status": "success",
  "data": {
    "booking_id": "hotel_for_trip-lambda-001",
    "trip_id": "trip-lambda-001",
    "status": "CANCELED"
  }
}
```

### 5.3 フライトキャンセル Lambda (`FlightCancelLambda`)

**イベントファイル**: `events/lambda/flight_cancel.json`

```bash
aws lambda invoke \
    --function-name $FLIGHT_CANCEL_FN \
    --payload file://events/lambda/flight_cancel.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== Response ===" && cat /tmp/response.json | jq .
```

**期待レスポンス** (`status` の表記は `CANCELLED`):
```json
{
  "status": "success",
  "data": {
    "booking_id": "flight_for_trip-lambda-001",
    "trip_id": "trip-lambda-001",
    "status": "CANCELLED"
  }
}
```

> **表記の違いについて**: Hotel サービスは `CANCELED`、Flight サービスは `CANCELLED` という表記になっています（既知の不整合）。

### 5.4 冪等性確認 (2回目のキャンセル)

同じイベントを再度送信して、キャンセル済みレコードに対する冪等性を確認します。

```bash
# フライトキャンセルを 2 回目実行
aws lambda invoke \
    --function-name $FLIGHT_CANCEL_FN \
    --payload file://events/lambda/flight_cancel.json \
    --cli-binary-format raw-in-base64-out \
    /tmp/response.json \
    && echo "=== 2nd Cancel Response ===" && cat /tmp/response.json | jq .
```

**期待レスポンス**:
```json
{
  "status": "success",
  "message": "Already cancelled or not found"
}
```

> **ポイント**: キャンセル済みのレコードに対して再度キャンセルしても、エラーにならずに正常終了します。これは Saga の補償トランザクションにおける冪等性の重要な特性です。Hotel / Payment でも同様の動作を確認できます。

### 5.5 キャンセル後の DynamoDB 確認

```bash
aws dynamodb scan \
    --table-name $BOOKING_TABLE_NAME \
    --filter-expression "PK = :pk" \
    --expression-attribute-values '{":pk": {"S": "TRIP#trip-lambda-001"}}' \
    | jq '.Items[] | {SK: .SK.S, status: .status.S}'
```

**期待値**: 全レコードの `status` が `CANCELLED` / `CANCELED` / `REFUNDED` になっていること。

## 6. まとめ

| Lambda 関数 | イベントファイル | 入力スキーマ | 検証ポイント |
|---|---|---|---|
| FlightReserveLambda | `flight_reserve.json` | `{trip_id, flight_details}` | 予約作成・DynamoDB 書き込み |
| HotelReserveLambda | `hotel_reserve.json` | `{trip_id, hotel_details}` | 予約作成・DynamoDB 書き込み |
| PaymentProcessLambda | `payment_process.json` | `{trip_id, amount, currency}` | 決済処理・DynamoDB 書き込み |
| FlightCancelLambda | `flight_cancel.json` | `{trip_id}` | キャンセル・冪等性 |
| HotelCancelLambda | `hotel_cancel.json` | `{trip_id}` | キャンセル・冪等性 |
| PaymentRefundLambda | `payment_refund.json` | `{trip_id}` | 払い戻し・冪等性 |
| GetTripLambda | `get_trip.json` | API GW V2 Event (`pathParameters.trip_id`) | 集計レスポンス・404 ハンドリング |
| ListTripsLambda | `list_trips.json` | API GW V2 Event | GSI クエリ・重複排除 |

**Saga Lambda と Step Functions の挙動の違い**:

| 観点 | Lambda 直接実行 | Step Functions 経由 |
|---|---|---|
| 初期ステータス | `PENDING` | `CONFIRMED` / `COMPLETED` |
| Payload ラッパー | 不要（直接 JSON） | `Payload` キーにネスト |
| トレース | 単体 Lambda のみ | Flame Graph で全連鎖を可視化 |
| エラーハンドリング | Lambda 単体のエラー | Saga 補償フローが自動実行 |

Step Functions を経由した E2E 検証については 👉 **[Hands-on 12: E2E Verification & Chaos Testing](./12_e2e_verification_and_chaos.md)** を参照してください。
