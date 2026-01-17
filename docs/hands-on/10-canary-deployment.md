# Hands-on 10: Canary Deployment

新しいバージョンの Lambda 関数をデプロイする際、いきなり100%のトラフィックを流すのではなく、一部のトラフィックのみを流して様子を見る「Canary リリース」を導入します。

## 1. 目的
*   AWS CodeDeploy と連携し、Lambda の段階的デプロイ (Traffic Shifting) を設定する。
*   CloudWatch Alarms を設定し、エラー率が上がった場合に自動でロールバックさせる。

## 2. CDK による実装

`aws_codedeploy` を使用して、Lambda 関数のデプロイ設定を変更します。

### 2.1 Alias と DeploymentGroup の設定

各 Lambda 関数定義において、`current_version` から `Alias` を作成し、それを CodeDeploy で管理させます。

```python
from aws_cdk import (
    aws_codedeploy as codedeploy,
    aws_lambda as _lambda,
    aws_cloudwatch as cloudwatch,
)

# ...

        # Alias の作成 (Prod エイリアス)
        alias = _lambda.Alias(
            self, "FlightReserveAlias",
            alias_name="Prod",
            version=flight_reserve_lambda.current_version,
        )

        # アラームの作成 (例: エラー率)
        failure_alarm = cloudwatch.Alarm(
            self, "FlightReserveFailureAlarm",
            metric=flight_reserve_lambda.metric_errors(),
            threshold=1,
            evaluation_periods=1,
        )

        # CodeDeploy 設定
        codedeploy.LambdaDeploymentGroup(
            self, "FlightReserveDeploymentGroup",
            alias=alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10PERCENT_5MINUTES,
            alarms=[failure_alarm],
        )
```

**注意**: Step Functions は Lambda の ARN を直接参照するのではなく、この `Alias` を参照するように変更する必要があります。

## 3. デプロイと確認

1.  変更を Push し、パイプライン経由でデプロイ。
2.  Lambda 関数にコード修正（ログ出力追加など）を加えて再度 Push。
3.  CodeDeploy コンソールでデプロイ状況を確認。
    *   最初の5分間は 10% のみが新バージョンに流れる。
    *   その間にエラーが発生すれば、即座に旧バージョンに切り戻る (Rollback)。
    *   問題なければ 100% に切り替わる。

## 4. 次のステップ

運用フェーズにおいて最も重要な「可視化」を行います。
Datadog を導入し、分散トレーシングとメトリクス監視を実現します。

👉 **[Hands-on 11: Observability (Datadog)](./11-observability-datadog.md)** へ進む
