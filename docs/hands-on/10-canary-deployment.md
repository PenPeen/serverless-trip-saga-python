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
from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_codedeploy as codedeploy
from aws_cdk import aws_lambda as _lambda
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

        self.flight_reserve_alias = self._create_canary_deployment(
            "FlightReserve", flight_reserve
        )
        self.hotel_reserve_alias = self._create_canary_deployment(
            "HotelReserve", hotel_reserve
        )
        self.payment_process_alias = self._create_canary_deployment(
            "PaymentProcess", payment_process
        )

    def _create_canary_deployment(
        self,
        name: str,
        fn: _lambda.Function,
    ) -> _lambda.Alias:
        alias = _lambda.Alias(
            self,
            f"{name}Alias",
            alias_name="Prod",
            version=fn.current_version,
        )

        error_rate_alarm = cloudwatch.Alarm(
            self,
            f"{name}ErrorRateAlarm",
            metric=cloudwatch.MathExpression(
                expression="(errors / invocations) * 100",
                using_metrics={
                    "errors": fn.metric_errors(statistic="Sum"),
                    "invocations": fn.metric_invocations(statistic="Sum"),
                },
                label=f"{name} Error Rate %",
                period=Duration.minutes(1),
            ),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        codedeploy.LambdaDeploymentGroup(
            self,
            f"{name}DeploymentGroup",
            alias=alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10_PERCENT_5_MINUTES,
            alarms=[error_rate_alarm],
        )

        return alias
```

#### アラーム設計のポイント

| 設計判断 | 内容 | 理由 |
|---------|------|------|
| **エラー率 (%) を使用** | `(errors / invocations) * 100` | 絶対数ではトラフィック量に依存してしまう。カナリア期間中は 10% のトラフィックしか流れないため、割合で判定する方が適切 |
| **threshold=5** | エラー率 5% 以上で発火 | `threshold=1`（1回のエラーで即ロールバック）は過敏すぎる。一時的なネットワークエラー等で誤ロールバックが頻発する |
| **evaluation_periods=2** | 2期間連続でしきい値を超えた場合にアラーム | 単発のスパイクを無視し、持続的な問題のみを検知する |
| **treat_missing_data=NOT_BREACHING** | データなし＝正常として扱う | カナリア期間中にトラフィックが少なく、メトリクスが発生しない場合に誤ロールバックを防止 |

#### 補償関数（cancel / refund）をカナリア対象にしない理由

補償関数（`flight_cancel`, `hotel_cancel`, `payment_refund`）はカナリアデプロイの対象外としています。

*   補償関数はサガのロールバック時にのみ呼ばれるため、通常トラフィックが少なくカナリアの統計的判定が機能しない。
*   カナリアデプロイ中に補償関数が失敗すると、サガが不整合な状態に陥るリスクがある。
*   補償関数の品質は、CI パイプラインのユニットテストで担保する。

### infra/constructs/orchestration.py (更新)

`Functions` オブジェクトを丸ごと受け取る設計から、個別の関数参照を受け取る設計に変更します。型を `IFunction` にすることで、`Function` と `Alias` の両方を受け取れるようにします。

```python
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct


class Orchestration(Construct):
    """Step Functions ステートマシーン"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        flight_reserve: _lambda.IFunction,
        flight_cancel: _lambda.IFunction,
        hotel_reserve: _lambda.IFunction,
        hotel_cancel: _lambda.IFunction,
        payment_process: _lambda.IFunction,
    ):
        super().__init__(scope, id)

        # フライト予約
        reserve_flight_task = tasks.LambdaInvoke(
            self,
            "ReserveFlight",
            lambda_function=flight_reserve,
            retry_on_service_exceptions=True,
            result_path="$.results.flight",
        )

        # ホテル予約
        reserve_hotel_task = tasks.LambdaInvoke(
            self,
            "ReserveHotel",
            lambda_function=hotel_reserve,
            retry_on_service_exceptions=True,
            result_path="$.results.hotel",
        )

        # 決済処理
        process_payment_task = tasks.LambdaInvoke(
            self,
            "ProcessPayment",
            lambda_function=payment_process,
            retry_on_service_exceptions=True,
            result_path="$.results.payment",
        )

        # ... 以降の補償タスク・ステートマシン定義は変更なし ...
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

from infra.constructs import Api, Database, Deployment, Functions, Layers, Orchestration


class ServerlessTripSagaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Database Construct
        database = Database(self, "Database")

        # Layers Construct
        layers = Layers(self, "Layers")

        # Functions Construct
        fns = Functions(
            self,
            "Functions",
            table=database.table,
            common_layer=layers.common_layer,
        )

        # Deployment Construct (カナリアデプロイ)
        deployment = Deployment(
            self,
            "Deployment",
            flight_reserve=fns.flight_reserve,
            hotel_reserve=fns.hotel_reserve,
            payment_process=fns.payment_process,
        )

        # Orchestration Construct (Alias を使用)
        orchestration = Orchestration(
            self,
            "Orchestration",
            flight_reserve=deployment.flight_reserve_alias,
            flight_cancel=fns.flight_cancel,
            hotel_reserve=deployment.hotel_reserve_alias,
            hotel_cancel=fns.hotel_cancel,
            payment_process=deployment.payment_process_alias,
        )

        Api(
            self,
            "Api",
            state_machine=orchestration.state_machine,
            get_trip=fns.get_trip,
            list_trips=fns.list_trips,
        )
```

**注意**: Step Functions の `Orchestration` Construct は Lambda の ARN を直接参照するのではなく、`Deployment` Construct が作成した `Alias` を参照するように変更します。補償関数（`flight_cancel`, `hotel_cancel`）は `Functions` から直接渡します。

## 3. デプロイと確認

1.  変更を Push し、パイプライン経由でデプロイ。
2.  Lambda 関数にコード修正（ログ出力追加など）を加えて再度 Push。
3.  CodeDeploy コンソールでデプロイ状況を確認。
    *   最初の5分間は 10% のみが新バージョンに流れる。
    *   その間にエラー率が 5% を超える状態が2分間続けば、自動で旧バージョンに切り戻る (Rollback)。
    *   問題なければ 100% に切り替わる。

## 4. 次のステップ

運用フェーズにおいて最も重要な「可視化」を行います。
Datadog を導入し、分散トレーシングとメトリクス監視を実現します。

👉 **[Hands-on 11: Observability (Datadog)](./11-observability-datadog.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/canary-deployment`
*   **コミットメッセージ**: `カナリアリリースの設定`
