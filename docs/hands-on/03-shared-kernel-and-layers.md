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
                    image=_lambda.Runtime.PYTHON_3_14.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output/python"
                    ],
                ),
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_14],
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

## 5. DDD Building Blocks の実装

DDDの戦術的パターンを適用するための基盤クラスを実装します。
これにより、各サービスで一貫したドメインモデルの構築が可能になります。

### 5.1 Entity 基底クラス (`services/shared/domain/entity.py`)

エンティティは識別子（ID）によって同一性が決まるオブジェクトです。

```python
from abc import ABC
from typing import Generic, TypeVar

ID = TypeVar("ID")


class Entity(ABC, Generic[ID]):
    """Entity 基底クラス

    エンティティは識別子によって同一性が決まる。
    同じIDを持つエンティティは、属性が異なっていても同一とみなす。
    """

    def __init__(self, id: ID) -> None:
        self._id = id

    @property
    def id(self) -> ID:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
```

### 5.2 AggregateRoot 基底クラス (`services/shared/domain/aggregate.py`)

集約ルートは、関連するエンティティ群の一貫性境界を定義します。
外部からのアクセスは必ず集約ルートを経由します。

```python
from typing import TypeVar
from services.shared.domain.entity import Entity

ID = TypeVar("ID")


class AggregateRoot(Entity[ID]):
    """AggregateRoot 基底クラス

    集約ルートは一貫性境界（Consistency Boundary）を定義する。
    - 配下のエンティティへのアクセスは必ず集約ルートを経由
    - トランザクション境界 = 集約境界
    """

    def __init__(self, id: ID) -> None:
        super().__init__(id)
        self._domain_events: list = []

    def add_domain_event(self, event: object) -> None:
        """ドメインイベントを追加（Outbox Pattern で利用）"""
        self._domain_events.append(event)

    def clear_domain_events(self) -> list:
        """ドメインイベントをクリアして返却"""
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events
```

### 5.3 Repository 抽象基底クラス (`services/shared/domain/repository.py`)

リポジトリは集約の永続化を抽象化します。
ドメイン層ではインターフェースのみを定義し、具象実装は Adapter 層で行います（依存性逆転の原則）。

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional

T = TypeVar("T")  # AggregateRoot type
ID = TypeVar("ID")  # ID type


class Repository(ABC, Generic[T, ID]):
    """Repository 抽象基底クラス

    集約の永続化を抽象化する。
    具象実装（DynamoDB, RDS等）は Adapter 層で行う。
    """

    @abstractmethod
    def save(self, aggregate: T) -> None:
        """集約を保存する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, id: ID) -> Optional[T]:
        """IDで集約を検索する"""
        raise NotImplementedError
```

### 5.4 Factory 基底クラス (`services/shared/domain/factory.py`)

ファクトリは複雑なオブジェクトの生成ロジックをカプセル化します。
ID生成、初期状態の設定、バリデーションなどを担当します。

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")  # 生成対象の型


class Factory(ABC, Generic[T]):
    """Factory 抽象基底クラス

    複雑なオブジェクト生成ロジックをカプセル化する。
    - ID生成（冪等性キーの生成など）
    - 初期状態の設定
    - 生成時バリデーション
    """

    @abstractmethod
    def create(self, *args, **kwargs) -> T:
        """オブジェクトを生成する"""
        raise NotImplementedError
```

### 5.5 ディレクトリ構成の更新

```
services/shared/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── exceptions.py    # 3.2 で作成済み
│   ├── entity.py        # 5.1 で追加
│   ├── aggregate.py     # 5.2 で追加
│   ├── repository.py    # 5.3 で追加
│   └── factory.py       # 5.4 で追加
└── utils/
    ├── __init__.py
    └── logger.py        # 3.1 で作成済み
```

### 5.6 `__init__.py` の更新 (`services/shared/domain/__init__.py`)

```python
from .exceptions import (
    DomainException,
    ResourceNotFoundException,
    BusinessRuleViolationException,
)
from .entity import Entity
from .aggregate import AggregateRoot
from .repository import Repository
from .factory import Factory

__all__ = [
    "DomainException",
    "ResourceNotFoundException",
    "BusinessRuleViolationException",
    "Entity",
    "AggregateRoot",
    "Repository",
    "Factory",
]
```

## 6. 次のステップ

共通基盤が整いました。いよいよ具体的な業務ロジックの実装に入ります。

👉 **[Hands-on 04: Service Implementation - Flight](./04-service-implementation-flight.md)** へ進む

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/shared-kernel`
*   **コミットメッセージ**: `共有カーネルの実装`
