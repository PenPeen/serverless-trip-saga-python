# Hands-on 08: API Gateway Integration
## 目的
* 外部アクセスのための API 構築
* Step Functions への Service Integration

## 実装
* API Gateway (REST API) を作成。
* `AwsIntegration` を使い、`StartExecution` アクションを直接コール。
* IAM Role で権限付与。

## 非同期APIの挙動 (Asynchronous Pattern)
* Step Functions への連携は**非同期**で行われます。
* クライアントには API Gateway から `200 OK` と共に `executionArn` (実行ID) が返却されます。
* **Note**: APIのレスポンス時点で「予約確約」ではありません（Eventual Consistency）。
    * 実際の予約結果を知るには、クライアントが別途ステータス確認APIをポーリングするか、WebSocket等で通知を受け取る仕組みが必要になることを理解してください。
