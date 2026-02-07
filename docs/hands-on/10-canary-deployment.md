# Hands-on 10: Canary Deployment

新しいバージョンの Lambda 関数をデプロイする際、いきなり100%のトラフィックを流すのではなく、一部のトラフィックのみを流して様子を見る「Canary リリース」を導入します。

## 1. 目的
*   AWS CodeDeploy と連携し、Lambda の段階的デプロイ (Traffic Shifting) を設定する。
*   CloudWatch Alarms を設定し、エラー率が上がった場合に自動でロールバックさせる。

## 2. CDK による実装

カナリアデプロイの設定を管理する Construct を作成します。

### Lambda Version と Alias について
安全なデプロイを行うために、以下の2つの概念を利用します。
1.  **Version (バージョン)**: デプロイ時点のコードと設定の不変なスナップショット。番号（1, 2, 3...）が振られます。
2.  **Alias (エイリアス)**: 特定のバージョンを指すポインタ（例: `Prod`）。
**CodeDeploy** は、この `Prod` エイリアスが指す先を「現在のバージョン」から「新しいバージョン」へ徐々に切り替える（重み付けを変える）ことで、トラフィック制御を実現します。

### ファイル構成
```
infra/
├── constructs/
│   ├── __init__.py
│   ├── database.py
│   ├── layers.py
│   ├── functions.py
│   ├── orchestration.py
│   ├── api.py
│   └── deployment.py    # カナリアデプロイ Construct (今回追加)
```

### infra/constructs/deployment.py
```python
from aws_cdk import (
    aws_codedeploy as codedeploy,
    aws_cloudwatch as cloudwatch,
    aws_lambda as _lambda,
)
from constructs import Construct


class Deployment(Construct):
    """カナリアデプロイを管理する Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        flight_reserve: _lambda.Function,
        hotel_reserve: _lambda.Function,
        payment_process: _lambda.Function,
    ) -> None:
        super().__init__(scope, id)

        # ========================================================================
        # Flight Reserve - カナリアデプロイ設定
        # ========================================================================
        self.flight_reserve_alias = _lambda.Alias(
            self, "FlightReserveAlias",
            alias_name="Prod",
            version=flight_reserve.current_version,
        )

        flight_failure_alarm = cloudwatch.Alarm(
            self, "FlightReserveFailureAlarm",
            metric=flight_reserve.metric_errors(),
            threshold=1,
            evaluation_periods=1,
        )

        codedeploy.LambdaDeploymentGroup(
            self, "FlightReserveDeploymentGroup",
            alias=self.flight_reserve_alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10PERCENT_5MINUTES,
            alarms=[flight_failure_alarm],
        )

        # ========================================================================
        # Hotel Reserve - カナリアデプロイ設定
        # ========================================================================
        self.hotel_reserve_alias = _lambda.Alias(
            self, "HotelReserveAlias",
            alias_name="Prod",
            version=hotel_reserve.current_version,
        )

        hotel_failure_alarm = cloudwatch.Alarm(
            self, "HotelReserveFailureAlarm",
            metric=hotel_reserve.metric_errors(),
            threshold=1,
            evaluation_periods=1,
        )

        codedeploy.LambdaDeploymentGroup(
            self, "HotelReserveDeploymentGroup",
            alias=self.hotel_reserve_alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10PERCENT_5MINUTES,
            alarms=[hotel_failure_alarm],
        )

        # ========================================================================
        # Payment Process - カナリアデプロイ設定
        # ========================================================================
        self.payment_process_alias = _lambda.Alias(
            self, "PaymentProcessAlias",
            alias_name="Prod",
            version=payment_process.current_version,
        )

        payment_failure_alarm = cloudwatch.Alarm(
            self, "PaymentProcessFailureAlarm",
            metric=payment_process.metric_errors(),
            threshold=1,
            evaluation_periods=1,
        )

        codedeploy.LambdaDeploymentGroup(
            self, "PaymentProcessDeploymentGroup",
            alias=self.payment_process_alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10PERCENT_5MINUTES,
            alarms=[payment_failure_alarm],
        )
```

### infra/constructs/\_\_init\_\_.py (更新)
```python
from .api import Api as Api
from .database import Database as Database
from .deployment import Deployment as Deployment
from .functions import Functions as Functions
from .layers import Layers as Layers
from .orchestration import Orchestration as Orchestration
```

### serverless_trip_saga_stack.py (更新)
```python
from aws_cdk import Stack
from constructs import Construct
from infra.constructs import Database, Layers, Functions, Orchestration, Api, Deployment


class ServerlessTripSagaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        database = Database(self, "Database")
        layers = Layers(self, "Layers")
        functions = Functions(
            self, "Functions",
            table=database.table,
            common_layer=layers.common_layer,
        )

        # Deployment Construct (カナリアデプロイ)
        deployment = Deployment(
            self, "Deployment",
            flight_reserve=functions.flight_reserve,
            hotel_reserve=functions.hotel_reserve,
            payment_process=functions.payment_process,
        )

        # Orchestration は Alias を参照するように変更
        orchestration = Orchestration(
            self, "Orchestration",
            flight_reserve=deployment.flight_reserve_alias,  # Alias を使用
            flight_cancel=functions.flight_cancel,
            hotel_reserve=deployment.hotel_reserve_alias,    # Alias を使用
            hotel_cancel=functions.hotel_cancel,
            payment_process=deployment.payment_process_alias, # Alias を使用
        )

        api = Api(
            self, "Api",
            state_machine=orchestration.state_machine,
            get_trip=functions.get_trip,
            list_trips=functions.list_trips,
        )
```

**注意**: Step Functions の `Orchestration` Construct は Lambda の ARN を直接参照するのではなく、`Deployment` Construct が作成した `Alias` を参照するように変更します。

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

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/canary-deployment`
*   **コミットメッセージ**: `カナリアリリースの設定`
