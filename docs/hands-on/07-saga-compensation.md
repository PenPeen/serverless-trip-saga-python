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

Hands-on 06 の定義を拡張します。

### 3.1 補償タスクの定義 (Cancel Lambda)

```python
        # Cancel Tasks
        cancel_hotel_task = tasks.LambdaInvoke(
            self, "CancelHotel",
            lambda_function=hotel_cancel_lambda,
            retry_on_service_exceptions=True, # 取り消し自体の失敗対策（リトライ）
        ).next(sfn.Fail(self, "HotelCancelled"))

        cancel_flight_task = tasks.LambdaInvoke(
            self, "CancelFlight",
            lambda_function=flight_cancel_lambda,
            retry_on_service_exceptions=True,
        ).next(sfn.Fail(self, "FlightCancelled"))
```

### 3.2 エラーハンドリング (add_catch) の追加

正常系タスクに `add_catch` を追加し、エラー時に補償タスクへ遷移させます。

```python
        # Payment 失敗 -> Hotel キャンセルへ
        process_payment_task.add_catch(
            cancel_hotel_task,
            result_path="$.error_info"
        )

        # Hotel 失敗 (および Payment失敗後のHotelキャンセル完了後) -> Flight キャンセルへ
        # 注意: チェーン構造を工夫する必要があります。
        # 実際には並列処理や、直列的な逆順実行フローを定義します。
```

*(実装のヒント: `cancel_hotel_task` の `next` を `cancel_flight_task` に繋げることで、連鎖的なロールバックを実現します)*

#### 改良後のチェーン例:
```python
        # ロールバックフローのチェーン: Cancel Hotel -> Cancel Flight -> Fail
        rollback_chain = cancel_hotel_task.next(cancel_flight_task).next(sfn.Fail(self, "SagaFailed"))

        # Payment 失敗時
        process_payment_task.add_catch(rollback_chain, ...)

        # Hotel 失敗時 (Hotelキャンセルは不要なので、直接Flightキャンセルへ)
        reserve_hotel_task.add_catch(cancel_flight_task, ...)
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
