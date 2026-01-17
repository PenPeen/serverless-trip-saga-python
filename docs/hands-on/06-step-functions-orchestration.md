# Hands-on 06: Saga Orchestration (Step Functions)
## 目的
* 正常系フローの構築

## 定義フロー
Start -> Reserve Flight -> Reserve Hotel -> Process Payment -> Succeed

## CDK実装
* `tasks.LambdaInvoke` を使用してチェーン (`.next()`) を定義。
* **データの受け渡し (Context Propagation)**:
    * 単純な `output_path="$.Payload"` ではなく、**`result_path`** の使用を推奨します（例: `result_path="$.results.flight"`）。
    * これにより、前のステップの入力データ（予約IDや顧客情報）を上書きせずに保持したまま、後続のステップや補償トランザクション（キャンセル処理）で参照可能になります。

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/step-functions`
*   **コミットメッセージ**: `Step Functionsによるオーケストレーション`
