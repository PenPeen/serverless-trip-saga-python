# Hands-on 11: Observability (Datadog / X-Ray)
## 目的
* 分散システムの可視化と監視

## 監視ツールの選択
本ハンズオンでは高度な監視機能を持つ **Datadog** の導入手順を解説しますが、AWS標準機能のみで完結させたい場合は **CloudWatch ServiceLens (X-Ray)** を使用することも可能です。

## CDK Construct への実装

可観測性の設定を管理する Construct を作成します。

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
│   ├── deployment.py
│   └── observability.py  # 可観測性 Construct (今回追加)
```

## パターンA: Datadog 実装 (Advanced)
* **前提**: Datadog アカウントと API Key が必要です。
* `datadog-cdk-constructs-v2` を使用。
* Lambda Extension の導入、Trace/Log の連携。
* Step Functions の可視化。

### infra/constructs/observability.py (Datadog版)
```python
from datadog_cdk_constructs_v2 import Datadog
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class Observability(Construct):
    """可観測性を管理する Construct (Datadog版)"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        functions: list[_lambda.Function],
        datadog_api_key_secret_arn: str,
    ) -> None:
        super().__init__(scope, id)

        datadog = Datadog(
            self, "Datadog",
            python_layer_version=<LATEST_VERSION>,
            extension_layer_version=<LATEST_VERSION>,
            api_key_secret_arn=datadog_api_key_secret_arn,
            enable_datadog_tracing=True,
            enable_datadog_logs=True,
        )

        for fn in functions:
            datadog.add_lambda_functions([fn])
```

## パターンB: AWS Native 実装 (Standard)
* **概要**: 追加アカウント不要で実装可能です。
* CDKで `tracing=Tracing.ACTIVE` を Lambda および Step Functions State Machine に設定。
* CloudWatch ServiceLens コンソールでサービスマップとトレースを確認。

### infra/constructs/observability.py (AWS Native版)
```python
from aws_cdk import (
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
)
from constructs import Construct


class Observability(Construct):
    """可観測性を管理する Construct (AWS Native版)"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        functions: list[_lambda.Function],
        state_machine: sfn.StateMachine,
    ) -> None:
        super().__init__(scope, id)

        # Lambda 関数に X-Ray トレーシングを有効化
        for fn in functions:
            fn.add_environment("AWS_XRAY_TRACING_NAME", fn.function_name)
```

**注意**: AWS Native版の場合、Lambda関数とStep Functions作成時に `tracing` パラメータを設定する必要があります。

### Functions Construct の更新 (AWS Native版)
```python
# infra/constructs/functions.py

        self.flight_reserve = _lambda.Function(
            self, "FlightReserveLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.flight.handlers.reserve.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            tracing=_lambda.Tracing.ACTIVE,  # X-Ray 有効化
            environment={...},
        )
```

### Orchestration Construct の更新 (AWS Native版)
```python
# infra/constructs/orchestration.py

        self.state_machine = sfn.StateMachine(
            self, "TripBookingStateMachine",
            definition=definition,
            tracing_enabled=True,  # X-Ray 有効化
        )
```

### infra/constructs/\_\_init\_\_.py (更新)
```python
from .database import Database
from .layers import Layers
from .functions import Functions
from .orchestration import Orchestration
from .api import Api
from .deployment import Deployment
from .observability import Observability

__all__ = [
    "Database", "Layers", "Functions", "Orchestration",
    "Api", "Deployment", "Observability"
]
```

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/observability`
*   **コミットメッセージ**: `可観測性の設定`
