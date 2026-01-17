# Hands-on 03: 共通基盤の実装 (Shared Kernel & Layers)

マイクロサービスアーキテクチャでは、コードの重複を避け、一貫性を保つための共通基盤が重要です。
本ハンズオンでは、外部ライブラリを Lambda Layers で管理し、ドメイン共通のロジックを「Shared Kernel」として実装します。

## 1. 目的
*   `aws-lambda-powertools` や `pydantic` などの依存ライブラリを Lambda Layer 化し、デプロイ時間を短縮する。
*   各マイクロサービスで共通利用する例外クラス、ログ設定、DDD基底クラスを実装し、開発効率と品質を向上させる。

## 2. Lambda Layer の構築 (依存ライブラリ)

Lambda 関数ごとに大きなライブラリをパッケージングするのを避けるため、Layer を作成します。

### 2.1 Layer 用ディレクトリの準備
プロジェクトルートに `layers` ディレクトリを作成し、依存関係定義を配置します。

```bash
mkdir -p layers/common_layer
```

`layers/common_layer/requirements.txt`:
```text
aws-lambda-powertools[all]
pydantic>=2.0.0
```

### 2.2 CDK スタックへの Layer 定義追加

CDK スタックファイル (`serverless_trip_saga_python_stack.py`) に、Layer の定義を追加します。

```python
from aws_cdk import (
    # ... 他のインポート
    aws_lambda as _lambda,
)

# ... クラス内
        # ========================================================================
        # Lambda Layer (Common Dependencies)
        # ========================================================================
        common_layer = _lambda.LayerVersion(
            self, "CommonLayer",
            code=_lambda.Code.from_asset(
                "layers/common_layer",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_9.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output/python"
                    ],
                ),
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
            description="Common dependencies (Powertools, Pydantic)",
        )
```
*(注: BundlingOptions を使用するには Docker が必要です。Dockerなしの場合は事前に `pip install -t` する方法もあります)*

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
