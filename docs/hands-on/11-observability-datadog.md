# Hands-on 11: Observability (Datadog)
## 目的
* 分散システムの可視化と監視

## 前提条件
* Datadog アカウントと API Key が必要です。
* `datadog-cdk-constructs-v2` を使用します。

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

## Datadog 実装

* Lambda Extension の導入、Trace/Log の連携。
* Step Functions の可視化。

### infra/constructs/observability.py
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
