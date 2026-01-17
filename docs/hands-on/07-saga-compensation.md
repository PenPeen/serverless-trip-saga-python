# Hands-on 07: Saga Compensation (Error Handling)

分散システムにおいて、一部の処理が失敗した際に、既に完了した処理を取り消して整合性を保つ仕組みが「補償トランザクション」です。
Step Functions のエラーハンドリング機能 (`add_catch`) を利用して、Saga パターンを完成させます。

## 1. 目的
*   Step Functions のエラーハンドリング (Catch) を実装する。
*   各サービスの「取り消し処理（補償トランザクション）」を呼び出す異常系フローを構築する。
*   失敗時にシステム全体がロールバックされることを確認する。

## 2. 補償トランザクションの設計

各ステップで失敗が発生した場合、それ以前に成功したステップの取り消し処理を実行する必要があります。

*   **Payment 失敗時**: -> Hotel Cancel -> Flight Cancel -> Fail
*   **Hotel 失敗時**: -> Flight Cancel -> Fail
*   **Flight 失敗時**: -> Fail (取り消し対象なし)

## 3. CDK による実装

Hands-on 06 で作成した `Orchestration` Construct を拡張し、補償トランザクションを追加します。

### infra/constructs/orchestration.py (更新)

```python
from aws_cdk import (
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as _lambda,
)
from constructs import Construct


class Orchestration(Construct):
    """Step Functions ステートマシンを管理する Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        flight_reserve: _lambda.Function,
        flight_cancel: _lambda.Function,
        hotel_reserve: _lambda.Function,
        hotel_cancel: _lambda.Function,
        payment_process: _lambda.Function,
    ) -> None:
        super().__init__(scope, id)

        # ========================================================================
        # 正常系タスク
        # ========================================================================
        reserve_flight_task = tasks.LambdaInvoke(
            self, "ReserveFlight",
            lambda_function=flight_reserve,
            result_path="$.results.flight",
        )

        reserve_hotel_task = tasks.LambdaInvoke(
            self, "ReserveHotel",
            lambda_function=hotel_reserve,
            result_path="$.results.hotel",
        )

        process_payment_task = tasks.LambdaInvoke(
            self, "ProcessPayment",
            lambda_function=payment_process,
            result_path="$.results.payment",
        )

        # ========================================================================
        # 補償タスク (Cancel)
        # 注意: Step Functions では同じタスクを複数のチェーンで再利用できないため、
        #       チェーンごとに別のタスクインスタンスを作成する
        # ========================================================================

        # Payment 失敗時のロールバック用
        cancel_hotel_from_payment = tasks.LambdaInvoke(
            self, "CancelHotelFromPayment",
            lambda_function=hotel_cancel,
            retry_on_service_exceptions=True,
            result_path="$.results.hotel_cancel",
        )

        cancel_flight_from_payment = tasks.LambdaInvoke(
            self, "CancelFlightFromPayment",
            lambda_function=flight_cancel,
            retry_on_service_exceptions=True,
            result_path="$.results.flight_cancel",
        )

        # Hotel 失敗時のロールバック用
        cancel_flight_from_hotel = tasks.LambdaInvoke(
            self, "CancelFlightFromHotel",
            lambda_function=flight_cancel,
            retry_on_service_exceptions=True,
            result_path="$.results.flight_cancel",
        )

        # ========================================================================
        # 失敗ステート (チェーンごとに別インスタンス)
        # ========================================================================
        saga_failed_from_payment = sfn.Fail(self, "SagaFailedFromPayment", error="SagaFailed")
        saga_failed_from_hotel = sfn.Fail(self, "SagaFailedFromHotel", error="SagaFailed")

        # ========================================================================
        # ロールバックチェーン
        # ========================================================================
        # Payment 失敗時: Hotel Cancel -> Flight Cancel -> Fail
        rollback_from_payment = (
            cancel_hotel_from_payment
            .next(cancel_flight_from_payment)
            .next(saga_failed_from_payment)
        )

        # Hotel 失敗時: Flight Cancel -> Fail
        rollback_from_hotel = cancel_flight_from_hotel.next(saga_failed_from_hotel)

        # ========================================================================
        # エラーハンドリング (add_catch)
        # ========================================================================
        process_payment_task.add_catch(
            rollback_from_payment,
            result_path="$.error_info"
        )

        reserve_hotel_task.add_catch(
            rollback_from_hotel,
            result_path="$.error_info"
        )

        # ========================================================================
        # State Machine Definition
        # ========================================================================
        definition = (
            reserve_flight_task
            .next(reserve_hotel_task)
            .next(process_payment_task)
            .next(sfn.Succeed(self, "BookingSucceeded"))
        )

        self.state_machine = sfn.StateMachine(
            self, "TripBookingStateMachine",
            definition=definition,
        )
```

### serverless_trip_saga_stack.py (更新)
```python
        # Orchestration Construct (補償トランザクション追加)
        orchestration = Orchestration(
            self, "Orchestration",
            flight_reserve=functions.flight_reserve,
            flight_cancel=functions.flight_cancel,
            hotel_reserve=functions.hotel_reserve,
            hotel_cancel=functions.hotel_cancel,
            payment_process=functions.payment_process,
        )
```

## 4. デプロイと検証（カオスエンジニアリング）

```bash
cdk deploy
```

### 4.1 疑似エラーによる動作確認
Payment Service のコードを一時的に修正し、必ず例外を投げるように変更（または入力パラメータでエラーを誘発させる）してデプロイします。

1.  ステートマシンを実行。
2.  Payment が失敗 (Red)。
3.  自動的に Cancel Hotel -> Cancel Flight が実行 (Green) されることを確認。
4.  DynamoDB を確認し、予約データが削除（またはキャンセルステータスに変更）されていることを確認。

## 5. 次のステップ

これで堅牢な予約システム（バックエンド）が完成しました。
次は、このシステムを外部（Webフロントエンドなど）から利用できるように、API を公開します。

👉 **[Hands-on 08: API Gateway Integration](./08-api-gateway-integration.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/saga-compensation`
*   **コミットメッセージ**: `Saga補償トランザクションの実装`
