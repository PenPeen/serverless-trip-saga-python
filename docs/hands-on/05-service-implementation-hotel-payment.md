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

## CDK Construct への定義追加

Hands-on 04 で作成した `Functions` Construct に、Hotel/Payment サービスの Lambda 関数を追加します。

### infra/constructs/functions.py (追加)
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
        # Flight Service Lambda (Hands-on 04 で作成済み)
        # ========================================================================
        self.flight_reserve = _lambda.Function(...)
        self.flight_cancel = _lambda.Function(
            self, "FlightCancelLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.flight.handlers.cancel.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "flight-service",
            },
        )

        # ========================================================================
        # Hotel Service Lambda (今回追加)
        # ========================================================================
        self.hotel_reserve = _lambda.Function(
            self, "HotelReserveLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.hotel.handlers.reserve.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "hotel-service",
            },
        )

        self.hotel_cancel = _lambda.Function(
            self, "HotelCancelLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.hotel.handlers.cancel.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "hotel-service",
            },
        )

        # ========================================================================
        # Payment Service Lambda (今回追加)
        # ========================================================================
        self.payment_process = _lambda.Function(
            self, "PaymentProcessLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.payment.handlers.process.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "payment-service",
            },
        )

        self.payment_refund = _lambda.Function(
            self, "PaymentRefundLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.payment.handlers.refund.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "payment-service",
            },
        )

        # DynamoDB への権限付与
        table.grant_write_data(self.flight_reserve)
        table.grant_write_data(self.flight_cancel)
        table.grant_write_data(self.hotel_reserve)
        table.grant_write_data(self.hotel_cancel)
        table.grant_write_data(self.payment_process)
        table.grant_write_data(self.payment_refund)
```

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/hotel-payment-service`
*   **コミットメッセージ**: `HotelおよびPaymentサービスの実装`
