# Hands-on 12: E2E Verification & Chaos Testing

本セクションでは、構築した Saga オーケストレーションの動作確認を行います。
正常系のシナリオだけでなく、意図的にエラーを発生させる「カオスエンジニアリング」の手法を用いて、補償トランザクション（ロールバック処理）が正しく機能することを検証します。

また、API Gateway を経由した外部からのリクエスト実行検証や、分散システム特有の「重複実行（冪等性）」の確認も行います。

## 目的

1.  **正常系**: 全ての予約処理（フライト、ホテル、決済）が完了し、データ整合性が保たれていることを確認する。
2.  **異常系 (Payment Fail)**: 決済失敗時に、既に完了したフライトとホテルの予約が自動的にキャンセルされることを確認する。
3.  **異常系 (Hotel Fail)**: ホテル予約失敗時に、既に完了したフライト予約がキャンセルされることを確認する。
4.  **API Gateway**: 外部公開されたエンドポイント経由でワークフローを開始できることを確認する。
5.  **重複実行**: 同じリクエストを再度送信した際の挙動を確認する。

## 前提条件

*   `cdk deploy` が完了していること。
*   検証用 JSON ファイルが `events/` ディレクトリに配置されていること。
*   AWS CLI, `curl`, `jq` が実行可能であること。
*   Datadog アカウントにアクセス可能であること（可観測性の確認のため）。

## 1. 環境変数の設定

検証コマンドを簡略化するため、Step Functions の ARN と DynamoDB テーブル名、API Gateway URL を環境変数に設定します。

```bash
# Step Functions ARN の取得
export STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines --query "stateMachines[?contains(name, 'TripBookingStateMachine')].stateMachineArn" --output text)
echo "State Machine ARN: $STATE_MACHINE_ARN"

# DynamoDB テーブル名の取得 (BookingTable -> TripTable に修正)
export BOOKING_TABLE_NAME=$(aws dynamodb list-tables --query "TableNames[?contains(@, 'TripTable')]" --output text)
echo "Booking Table Name: $BOOKING_TABLE_NAME"

# API Gateway URL の取得 (Stack名依存を排除し、API名から直接取得)
export API_URL=$(aws apigatewayv2 get-apis --query "Items[?Name=='Trip Booking API'].ApiEndpoint" --output text)
echo "API URL: $API_URL"
```

## 2. 正常系シナリオ (Happy Path) - Step Functions 直接実行

まずは AWS CLI を使って Step Functions を直接実行し、ロジックの正当性を確認します。

### 2.1 実行

```bash
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Verification-Success-$(date +%s)" \
    --input file://events/sfn_input_success.json
```

### 2.2 結果確認 (AWS Console & CLI)

ステータスが `SUCCEEDED` になるまで待ちます。

```bash
# 最新の実行結果を取得
aws stepfunctions list-executions \
    --state-machine-arn $STATE_MACHINE_ARN \
    --max-items 1
```

**AWS Console での確認方法:**
1.  Step Functions コンソールを開く。
2.  `TripBookingStateMachine` を選択。
3.  最新の実行（Verification-Success-...）をクリック。
4.  **Graph View** で、全てのステップが緑色（成功）になっていることを確認。

### 2.3 データ確認 (DynamoDB)

予約データが「確定 (CONFIRMED / COMPLETED)」状態で保存されていることを確認します。

```bash
aws dynamodb scan \
    --table-name $BOOKING_TABLE_NAME \
    --filter-expression "PK = :pk" \
    --expression-attribute-values '{":pk": {"S": "TRIP#trip-success-001"}}'
```
> **期待値**: 全てのアイテム（FLIGHT, HOTEL, PAYMENT）が存在し、status が `CONFIRMED` または `COMPLETED` であること。

### 2.4 可観測性の確認 (Datadog)

この実行が Datadog でどのように見えるかを確認します。

1.  **Datadog > Serverless > Step Functions** を開く。
2.  `OrchestrationTripBookingStateMachine` を選択。
3.  画面下部の **Executions** タブから、先ほどの実行を選択。
4.  **Flame Graph** で、Step Functions -> 各 Lambda (ReserveFlight, ReserveHotel, ProcessPayment) の呼び出しが繋がっていることを確認する。
5.  もし Lambda のログが見たい場合、Flame Graph 上の Lambda Span をクリックし、Logs タブを選択する。

## 3. 正常系シナリオ - API Gateway 経由実行

次に、API Gateway のエンドポイント (`POST /trips`) を叩いてワークフローを開始します。
これは Web フロントエンドやモバイルアプリからの利用を想定したシナリオです。

### 3.1 リクエスト形式について
現在、API Gateway にはマッピングテンプレート (VTL) が設定されています。
これにより、クライアントは純粋な JSON データを送信するだけで、API Gateway が自動的に Step Functions の入力形式に変換してくれます。
面倒な JSON のエスケープ処理 (`{\"input\": ...}`) は不要になりました。

**送信するデータ:**
```json
{ "trip_id": "trip-api-001", ... }
```

### 3.2 実行 (curl)

`jq` コマンドで JSON ファイルを読み込み、そのまま API Gateway へ送信します。

```bash
# 1. 検証用データの trip_id をユニークなものに変更 (衝突回避)
jq '.trip_id = "trip-api-success-001"' events/sfn_input_success.json > events/sfn_input_api.json

# 2. curl で POST リクエスト送信
# 以前のような複雑な jq 処理は不要です
curl -X POST "$API_URL/trips" \
  -H "Content-Type: application/json" \
  -d @events/sfn_input_api.json
```

### 3.3 結果確認

API からは `executionArn` と `startDate` が返却されます。

**AWS Console での確認 (CloudWatch):**
現在の設定では、API Gateway のログは Datadog に転送されていません（別途設定が必要）。そのため、AWS コンソールで確認します。

1.  **API Gateway コンソール** を開く。
2.  `Trip Booking API` を選択 -> **Monitor** タブを見る。
3.  または、CloudWatch Logs で `/aws/apigateway/...` (設定されている場合) のロググループを確認する。
    *   ※今回のハンズオン構成 (`HttpApi`) ではデフォルトでアクセスログが無効になっている場合があります。その場合は、Step Functions 側で実行が開始されたこと (`executionArn` が返ること) をもって成功とみなします。

**Datadog での確認 (Step Functions):**
API Gateway のログは見れませんが、そこからキックされた Step Functions の実行は Datadog で確認できます。

1.  **Datadog > Serverless > Step Functions**。
2.  新しい実行履歴（Start time が直近のもの）が表示されていることを確認。

## 4. 重複実行の検証 (Idempotency Check)

分散システムでは、ネットワーク遅延などにより同じリクエストが複数回到達する可能性があります。
ここでは、既に成功したリクエストと同じ `trip_id` で再度実行した場合の挙動を確認します。

### 4.1 実行

先ほど成功した `trip-success-001` を入力として、再度実行します。

```bash
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Verification-Duplicate-$(date +%s)" \
    --input file://events/sfn_input_success.json
```

### 4.2 結果確認

実行ステータスを確認します。

```bash
aws stepfunctions list-executions \
    --state-machine-arn $STATE_MACHINE_ARN \
    --max-items 1
```

> **期待値**: ステータスは `FAILED` になります。
> **理由**: DynamoDB への書き込み時に `ConditionalCheckFailedException`（重複エラー）が発生するため。

**Datadog での確認:**
1.  Datadog でこの実行 (`FAILED`) を探す。
2.  エラーになっている Lambda (ReserveFlight) のログを確認する。
3.  `ConditionalCheckFailedException` というエラーログが出力されていることを確認する。

## 5. 異常系シナリオ: 決済失敗 (Saga Compensation - Payment)

ここからは異常系の動作確認です。
`amount` に負の値 (`-1`) を設定することで、バリデーションエラーを誘発させます。

### 5.1 実行

```bash
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Verification-PaymentFail-$(date +%s)" \
    --input file://events/sfn_input_payment_fail.json
```

### 5.2 結果確認

Step Functions の実行ステータスは `FAILED` になりますが、Graph View で補償フローが実行されたことを確認します。

**Datadog での確認:**
1.  Flame Graph を見る。
2.  `ProcessPayment` がエラー（赤色）になっている。
3.  その後に `CancelHotel` -> `CancelFlight` が順次実行されている（補償トランザクション）様子を確認する。

### 5.3 データ確認 (DynamoDB)

予約データが「キャンセル済み (CANCELLED)」状態に変更されていることを確認します。

```bash
aws dynamodb scan \
    --table-name $BOOKING_TABLE_NAME \
    --filter-expression "PK = :pk" \
    --expression-attribute-values '{":pk": {"S": "TRIP#trip-payment-fail-001"}}'
```

## 6. 異常系シナリオ: ホテル予約失敗 (Saga Compensation - Hotel)

ホテル予約でエラー（例: 日付不正）が発生した場合をシミュレーションします。

### 6.1 実行

```bash
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Verification-HotelFail-$(date +%s)" \
    --input file://events/sfn_input_hotel_fail.json
```

### 6.2 データ確認 (DynamoDB)

```bash
aws dynamodb scan \
    --table-name $BOOKING_TABLE_NAME \
    --filter-expression "PK = :pk" \
    --expression-attribute-values '{":pk": {"S": "TRIP#trip-hotel-fail-001"}}'
```
> **期待値**: `FLIGHT#...` のレコードの status が `CANCELLED` になっていること。

## 7. まとめ

これで、Step Functions 直接実行、API Gateway 経由実行、そして重複実行時の挙動検証が完了しました。
Saga パターンの整合性と、外部インターフェースの疎通確認が取れました。
また、AWS Console と Datadog の両方を使って、実行結果やエラー原因を追跡する方法も学びました。

さらに深い可観測性のテクニックについては、次章を参照してください。
👉 **[Hands-on 13: Advanced Observability with Datadog](./13_advanced_observability_datadog.md)** へ進む
