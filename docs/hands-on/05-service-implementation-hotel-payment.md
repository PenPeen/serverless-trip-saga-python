# Hands-on 05: Service Implementation - Hotel & Payment
## 目的
* Shared Kernel を活用した残りのサービス実装

## 実装内容
* **Hotel Service**: 予約 (Reserve) と キャンセル (Cancel)
* **Payment Service**: 決済 (Process) と 払い戻し (Refund)

## 冪等性 (Idempotency) の実装
* **重要性**: ネットワーク再送やリトライによる「二重決済」や「二重予約」を防ぐため、Lambda Powertools の Idempotency 機能を導入します。
* **永続化ストア**: 冪等性トークンを管理するための永続化層が必要です。
    * 本ハンズオンでは、Step 02 で作成したテーブルを使用します（別途 `IDEMPOTENCY#<key>` のようなキー設計を行うか、専用テーブルを作成するコードを追加します）。

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/hotel-payment-service`
*   **コミットメッセージ**: `HotelおよびPaymentサービスの実装`
