# Hands-on 03: 共通基盤の実装 (Shared Kernel & Layers)

マイクロサービスアーキテクチャ及びDDDでは、コードの重複を避け、一貫性を保つための共通基盤が重要です。
本ハンズオンでは、外部ライブラリを Lambda Layers で管理し、ドメイン共通のロジックを「Shared Kernel」として実装します。

## 1. 目的
*   `aws-lambda-powertools` や `pydantic` などの依存ライブラリを Lambda Layer 化し、デプロイ時間を短縮する。
*   複数のマイクロサービス間で共有する「Shared Kernel」を構築し、その中に例外クラス、ログ設定、DDD基底クラス（Entity, ValueObject など）を実装することで、開発効率と品質を向上させる。

## 2. Lambda Layer の構築 (依存ライブラリ)

Lambda 関数ごとに大きなライブラリをパッケージングするのを避けるため、Layer を作成します。

### 2.1 Layer 用ディレクトリの準備
プロジェクトルートに `layers` ディレクトリを作成し、依存関係定義を配置します。

```bash
mkdir -p layers/common_layer
```

`layers/common_layer/requirements.txt`:
```text
aws-lambda-powertools
pydantic>=2.0.0
```

### 2.2 CDK Construct への Layer 定義追加

Lambda Layer を管理する Construct を作成します。

#### ファイル構成
```
infra/
├── constructs/
│   ├── __init__.py
│   ├── database.py      # Hands-on 02 で作成済み
│   └── layers.py        # Lambda Layers Construct (今回追加)
```

#### infra/constructs/layers.py
```python
from aws_cdk import (
    BundlingOptions,
    aws_lambda as _lambda,
)
from constructs import Construct


class Layers(Construct):
    """Lambda Layers を管理する Construct"""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        # Common Layer (Powertools, Pydantic)
        self.common_layer = _lambda.LayerVersion(
            self, "CommonLayer",
            code=_lambda.Code.from_asset(
                "layers/common_layer",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output/python"
                    ],
                ),
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Common dependencies (Powertools, Pydantic)",
        )
```
*(注: BundlingOptions を使用するには Docker が必要です。Dockerなしの場合は事前に `pip install -t` する方法もあります)*

#### infra/constructs/\_\_init\_\_.py (更新)
```python
from .database import Database
from .layers import Layers

__all__ = ["Database", "Layers"]
```

#### serverless_trip_saga_stack.py (更新)
```python
from aws_cdk import Stack
from constructs import Construct
from infra.constructs import Database, Layers


class ServerlessTripSagaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Database Construct
        database = Database(self, "Database")

        # Layers Construct
        layers = Layers(self, "Layers")

        # 他の Construct から参照する場合:
        # - database.table
        # - layers.common_layer
```

## 3. Shared Kernel の実装 (共通コード)

`services/shared` ディレクトリに、全サービスで利用するコードを実装します。

### 3.1 構造化ロギング設定 (`services/shared/utils/logger.py`)

Powertools の Logger をラップし、共通の設定（サービス名の付与など）を行います。

```python
from aws_lambda_powertools import Logger

def get_logger(service_name: str) -> Logger:
    return Logger(service=service_name)
```

### 3.2 共通例外クラス (`services/shared/domain/exceptions.py`)

ビジネスロジックで発生するエラーを統一的に扱うための基底クラスです。

```python
class DomainException(Exception):
    """ドメイン層で発生する基底例外"""
    pass

class ResourceNotFoundException(DomainException):
    """リソースが見つからない場合"""
    pass

class BusinessRuleViolationException(DomainException):
    """ビジネスルールに違反した場合"""
    pass
```

## 4. デプロイと確認

作成した Layer をデプロイします。

```bash
cdk deploy
```

マネジメントコンソールの Lambda > Layers に `ServerlessTripSaga...CommonLayer` が作成されていることを確認します。

## 5. 次のステップ

共通基盤が整いました。いよいよ具体的な業務ロジックの実装に入ります。

👉 **[Hands-on 04: Service Implementation - Flight](./04-service-implementation-flight.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/shared-kernel`
*   **コミットメッセージ**: `共有カーネルの実装`
