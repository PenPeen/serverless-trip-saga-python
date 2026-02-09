# Hands-on 09: CI/CD Pipeline (CodePipeline)

継続的デリバリーを実現するため、AWS CodePipeline を使用して、GitHub へのプッシュをトリガーに自動テストとデプロイを行うパイプラインを構築します。

## 1. 目的
*   CDK Pipelines を使用して、Infrastructure as Code 自体のデプロイパイプラインを定義する。
*   ビルドプロセスに単体テスト (`pytest`) を組み込み、品質を担保する。
*   **本番デプロイ前に手動承認ステップを設け、意図しないリリースを防止する。**
*   GitHub リポジトリとの連携を行う。

## 2. パイプライン構成

1.  **Source**: GitHub (main branch)
2.  **Build (Synth)**: CDK Synth 実行 + **Unit Test 実行**
3.  **Deploy (UpdatePipeline)**: パイプライン自体の自己更新
4.  **Deploy (Assets)**: Lambda, Layer 等のアセットアップロード
5.  **Manual Approval**: 承認者がデプロイ内容を確認し、承認 or 却下
6.  **Deploy (Prod)**: アプリケーションスタックの本番デプロイ

## 3. 承認フローの設計

### 基本方針

本番環境へのデプロイには必ず手動承認を必須とし、テスト通過後もワンクッション挟むことで安全性を確保します。

### 複数 PR が短期間にマージされた場合の挙動

CodePipeline はデフォルトで **「最新のコミットだけを処理する」** 動作になります。具体的には以下の通りです。

*   パイプラインが実行中に新しいコミットが `main` に Push されると、現在の実行が完了した後に最新のソースで新しい実行が自動的に開始されます。
*   承認待ち中に新しいコミットが来た場合、**古い実行を却下（Reject）し、最新の実行で改めて承認する** 運用とします。これにより、常に最新のコードが本番に反映されます。

この挙動は CodePipeline のデフォルト（Superseded モード）であり、追加設定は不要です。

> **運用ルール**: 承認待ちのパイプラインがある状態で新しい PR がマージされた場合、古い実行は自動的に Superseded（取り替え）されます。承認者は常に最新の実行のみを承認してください。

## 4. CDK によるパイプライン定義

CI/CD パイプラインはアプリケーションスタックとは別に管理します。

### ファイル構成
```
infra/
├── constructs/          # アプリケーション用 Construct (既存)
│   ├── database.py
│   ├── layers.py
│   ├── functions.py
│   ├── orchestration.py
│   └── api.py
pipeline_stack.py        # CI/CD パイプライン (別Stack)
serverless_trip_saga_stack.py
```

### pipeline_stack.py
```python
from aws_cdk import (
    Stack,
    Stage,
    pipelines,
)
from constructs import Construct
from serverless_trip_saga_stack import ServerlessTripSagaStack


class ApplicationStage(Stage):
    """アプリケーションスタックをまとめるステージ"""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ServerlessTripSagaStack(self, "ServerlessTripSaga")


class PipelineStack(Stack):
    """CI/CD パイプラインを定義するスタック"""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        pipeline = pipelines.CodePipeline(
            self, "Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.connection(
                    "my-org/my-repo", "main",
                    connection_arn="arn:aws:codestar-connections:..."  # 事前に作成が必要
                ),
                commands=[
                    "npm install -g aws-cdk",
                    "pip install -r requirements.txt",
                    "pip install -r layers/common_layer/requirements.txt",  # テスト用に依存解決
                    "pytest tests/unit",  # テスト実行！ここが失敗するとデプロイされない
                    "cdk synth"
                ]
            )
        )

        # ---- 本番ステージ（承認フロー付き） ----
        pipeline.add_stage(
            ApplicationStage(self, "Prod"),
            pre=[
                pipelines.ManualApprovalStep(
                    "PromoteToProd",
                    comment="本番環境へデプロイします。Synth・テスト結果を確認のうえ承認してください。"
                )
            ]
        )
```

### app.py (更新)
```python
import aws_cdk as cdk
from serverless_trip_saga_stack import ServerlessTripSagaStack
from pipeline_stack import PipelineStack

app = cdk.App()

# 開発環境: 直接デプロイ用
ServerlessTripSagaStack(app, "ServerlessTripSagaDev")

# 本番環境: パイプライン経由（承認フロー付き）
PipelineStack(app, "PipelineStack")

app.synth()
```

*注: GitHub Connection は事前に AWS コンソールで作成し、ARN を取得しておく必要があります。*

## 5. 承認通知の設定（推奨）

承認リクエストが発生したことをチームに通知するため、SNS トピックを活用します。CodePipeline の Manual Approval アクションには SNS トピックを関連付けることができ、承認待ちになると自動的にメール等で通知が届きます。

CDK Pipelines の `ManualApprovalStep` では SNS トピックの直接指定はサポートされていないため、パイプライン生成後に EventBridge ルールで補完します。

```python
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs

# 承認通知用 SNS トピック
approval_topic = sns.Topic(self, "ApprovalNotification",
    display_name="Pipeline Approval Notification"
)
approval_topic.add_subscription(
    subs.EmailSubscription("team-lead@example.com")
)

# EventBridge で承認待ちイベントを検知
events.Rule(self, "ApprovalRule",
    event_pattern=events.EventPattern(
        source=["aws.codepipeline"],
        detail_type=["CodePipeline Action Execution State Change"],
        detail={
            "type": {
                "category": ["Approval"]
            },
            "state": ["STARTED"]
        }
    ),
    targets=[targets.SnsTopic(approval_topic)]
)
```

## 6. デプロイ手順

1.  パイプラインスタックを初回のみ手動デプロイします。
    ```bash
    cdk deploy PipelineStack
    ```
2.  以降は、コードを GitHub に Push するだけでパイプラインが稼働します。
3.  Synth・テストが通過すると**承認待ち**になります。SNS 通知が届いたら、CodePipeline コンソールで内容を確認し、承認（Approve）します。

## 7. 確認

*   CodePipeline コンソールでパイプラインの進行状況を確認。
*   わざとテストが失敗するコードを Push し、ビルドフェーズで止まる（承認ステップに到達しない）ことを確認。
*   テスト通過後、承認ステップで「却下（Reject）」を押し、デプロイが実行されないことを確認。
*   短期間に2つの PR をマージし、古い実行が Superseded され最新の実行のみが承認待ちになることを確認。

## 8. 運用フロー図

```
PR マージ (#1)          PR マージ (#2)
    |                       |
    v                       |
+----------+                |
|  Source   |                |
+----+-----+                |
     v                      v
+----------+          +----------+
|  Synth   |          |  Source   |  <-- 最新ソースで新しい実行が開始
| + Test   |          +----+-----+
+----+-----+               v
     v              +----------+
+----------+        |  Synth   |
| Approval |        | + Test   |
| (待ち)   |        +----+-----+
+----+-----+             v
     |              +----------+
  Superseded        | Approval |  <-- この実行のみ承認すればOK
  (自動取消)        | (待ち)   |
                    +----+-----+
                         v Approve
                    +----------+
                    |  Deploy   |  <-- #1 + #2 の両方を含む最新コード
                    |  (Prod)   |
                    +----------+
```

## 9. 次のステップ

安全にデプロイする仕組みはできましたが、一度に全トラフィックを切り替えるのはリスクがあります。
次は、段階的なデプロイ（カナリアリリース）を設定します。

👉 **[Hands-on 10: Canary Deployment](./10-canary-deployment.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/cicd-pipeline`
*   **コミットメッセージ**: `CI/CDパイプラインの構築（承認フロー付き）`
