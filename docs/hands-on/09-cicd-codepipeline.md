# Hands-on 09: CI/CD Pipeline (CodePipeline)

継続的デリバリーを実現するため、AWS CodePipeline を使用して、GitHub へのプッシュをトリガーに自動テストとデプロイを行うパイプラインを構築します。

## 1. 目的
*   CDK Pipelines を使用して、Infrastructure as Code 自体のデプロイパイプラインを定義する。
*   ビルドプロセスに単体テスト (`pytest`) を組み込み、品質を担保する。
*   GitHub リポジトリとの連携を行う。

## 2. パイプライン構成

1.  **Source**: GitHub (source branch)
2.  **Build (Synth)**: CDK Synth 実行 + **Unit Test 実行**
3.  **Deploy (UpdatePipeline)**: パイプライン自体の自己更新
4.  **Deploy (Assets)**: Lambda, Layer 等のアセットアップロード
5.  **Deploy (Staging)**: アプリケーションスタックのデプロイ

## 3. CDK によるパイプライン定義

新しい Stack ファイル `pipeline_stack.py` を作成（または既存 Stack と分離）することを推奨します。

```python
from aws_cdk import (
    Stack,
    pipelines as pipelines,
)

class PipelineStack(Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)

        pipeline = pipelines.CodePipeline(
            self, "Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.connection(
                    "my-org/my-repo", "main",
                    connection_arn="arn:aws:codestar-connections:..." # 事前に作成が必要
                ),
                commands=[
                    "npm install -g aws-cdk",
                    "pip install -r requirements.txt",
                    "pip install -r layers/common_layer/requirements.txt", # テスト用に依存解決
                    "pytest tests/unit", # テスト実行！ここが失敗するとデプロイされない
                    "cdk synth"
                ]
            )
        )
        
        # アプリケーションステージの追加
        pipeline.add_stage(MyApplicationStage(self, "Prod"))
```

*注: GitHub Connection は事前に AWS コンソールで作成し、ARN を取得しておく必要があります。*

## 4. デプロイ手順

1.  パイプラインスタックを初回のみ手動デプロイします。
    ```bash
    cdk deploy PipelineStack
    ```
2.  以降は、コードを GitHub に Push するだけでパイプラインが稼働します。

## 5. 確認

*   CodePipeline コンソールでパイプラインの進行状況を確認。
*   わざとテストが失敗するコードを Push し、ビルドフェーズで止まる（デプロイされない）ことを確認。

## 6. 次のステップ

安全にデプロイする仕組みはできましたが、一度に全トラフィックを切り替えるのはリスクがあります。
次は、段階的なデプロイ（カナリアリリース）を設定します。

👉 **[Hands-on 10: Canary Deployment](./10-canary-deployment.md)** へ進む
