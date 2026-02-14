# Hands-on 11: Observability (Datadog)
## 目的
* 分散システムの可視化と監視 (Lambda & Step Functions)

## 前提条件
* Datadog アカウントと API Key が必要です。
* `datadog-cdk-constructs-v2` を使用します。

## 事前準備: SSM Parameter Store への API Key 登録

Datadog の API Key を SSM Parameter Store に SecureString として登録します。
これは CDK デプロイの **前に** 1回だけ実行してください。

```bash
aws ssm put-parameter \
  --name "/serverless-trip-saga/datadog-api-key" \
  --type SecureString \
  --value "<YOUR_DATADOG_API_KEY>"
```

> **Note**: パラメータ名を変更する場合は、`Observability` Construct の `datadog_api_key_ssm_parameter_name` 引数も合わせて変更してください。

## アーキテクチャ

```
SSM Parameter Store (SecureString)
  └─→ Secrets Manager Secret (CDK が自動作成)
        ├─→ Datadog Forwarder (公式 CFn テンプレートを Nested Stack でデプロイ)
        └─→ Datadog Lambda Layer (API Key 参照)

Datadog Forwarder
  └─→ Step Functions トレース転送

Datadog Lambda Layer
  └─→ Lambda メトリクス / トレース / ログ送信
```

## 依存関係の追加

`pyproject.toml` に以下の依存関係を追加します。

```toml
[dependency-groups]
dev = [
    # ... 他の依存関係
    "datadog-cdk-constructs-v2>=1.0.0",
]
```

## CDK Construct への実装

### 1. Functions Construct の改修

全ての Lambda 関数を一括で Datadog に登録できるように、`infra/constructs/functions.py` で関数リストを公開します。

```python
# infra/constructs/functions.py

class Functions(Construct):
    def __init__(self, ...):
        # ... 既存の関数定義 ...

        # Datadog 適用用に全関数をまとめたリストを公開
        self.all_functions = [
            self.flight_reserve,
            self.flight_cancel,
            self.hotel_reserve,
            self.hotel_cancel,
            self.payment_process,
            self.payment_refund,
            self.get_trip,
            self.list_trips,
        ]
```

### 2. Observability Construct の作成

SSM Parameter Store の API Key を起点に、Secret / Forwarder / 計装を **自己完結的に構築** する Construct です。

**ファイル構成**:
```
infra/
└── constructs/
    └── observability.py
```

**`infra/constructs/observability.py`**:

```python
from datadog_cdk_constructs_v2 import Datadog, DatadogStepFunctions
from aws_cdk import (
    CfnStack,
    RemovalPolicy,
    SecretValue,
    aws_lambda as _lambda,
    aws_secretsmanager as secretsmanager,
    aws_stepfunctions as sfn,
)
from constructs import Construct


class Observability(Construct):
    """可観測性を管理する Construct (Datadog版)

    SSM Parameter Store の API Key を起点に、以下を自己完結的に構築する:
    1. Secrets Manager Secret (SSM SecureString から動的参照)
    2. Datadog Forwarder (公式 CloudFormation テンプレートを CfnStack でデプロイ)
    3. Lambda / Step Functions の Datadog 計装
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        functions: list[_lambda.Function],
        state_machine: sfn.StateMachine,
        datadog_api_key_ssm_parameter_name: str = "/serverless-trip-saga/datadog-api-key",
        service_name: str = "serverless-trip-saga",
        env: str = "dev",
    ) -> None:
        super().__init__(scope, id)

        # 1. Secrets Manager Secret の作成
        api_key_secret = secretsmanager.Secret(
            self,
            "DatadogApiKeySecret",
            secret_string_value=SecretValue.ssm_secure(
                datadog_api_key_ssm_parameter_name
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 2. Datadog Forwarder のデプロイ (Nested Stack)
        forwarder_stack = CfnStack(
            self,
            "DatadogForwarder",
            template_url="https://datadog-cloudformation-template.s3.amazonaws.com/aws/forwarder/latest.yaml",
            parameters={
                "DdApiKeySecretArn": api_key_secret.secret_arn,
                "DdSite": "datadoghq.com",
                "FunctionName": f"{service_name}-datadog-forwarder",
            },
        )

        forwarder_arn = forwarder_stack.get_att(
            "Outputs.DatadogForwarderArn"
        ).to_string()

        # 3. Lambda Functions の計装
        datadog_lambda = Datadog(
            self,
            "DatadogLambda",
            python_layer_version=122,
            extension_layer_version=92,
            api_key_secret_arn=api_key_secret.secret_arn,
            enable_datadog_tracing=True,
            enable_datadog_logs=True,
            capture_lambda_payload=True,
            site="datadoghq.com",
            service=service_name,
            env=env,
        )
        datadog_lambda.add_lambda_functions(functions)

        # 4. Step Functions の計装
        datadog_sfn = DatadogStepFunctions(
            self,
            "DatadogSfn",
            env=env,
            service=service_name,
            version="1.0.0",
            forwarder_arn=forwarder_arn,
            enable_step_functions_tracing=True,
        )
        datadog_sfn.add_state_machines([state_machine])
```

### 3. Stack への組み込み

`serverless_trip_saga_stack.py` では、`Observability` に `functions` と `state_machine` を渡すだけです。
Secret の作成や Forwarder のデプロイは Construct 内部で自動的に行われます。

```python
# serverless_trip_saga_stack.py

from infra.constructs import (
    Api,
    Database,
    Deployment,
    Functions,
    Layers,
    Observability,
    Orchestration,
)


class ServerlessTripSagaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ... (他の Construct の初期化) ...

        Observability(
            self,
            "Observability",
            functions=fns.all_functions,
            state_machine=orchestration.state_machine,
        )
```

## パイプライン互換性

SSM Parameter Store の動的参照 (`SecretValue.ssm_secure()`) は **CloudFormation デプロイ時** に解決されます。
そのため、CodeBuild や `pipeline_stack.py` の変更は不要です。

- `cdk synth` 時: SSM パラメータの値は参照されない（CloudFormation テンプレートに動的参照トークンが埋め込まれる）
- CloudFormation Deploy 時: AWS が SSM Parameter Store から値を取得し、Secret に設定する

## クリーンアップ

### `cdk destroy` で削除されるリソース
- Secrets Manager Secret (`RemovalPolicy.DESTROY` を指定済み)
- Datadog Forwarder Lambda (Nested Stack として管理)
- Datadog Lambda Layer の設定

### 手動で削除が必要なリソース
- SSM Parameter Store のパラメータ

```bash
aws ssm delete-parameter \
  --name "/serverless-trip-saga/datadog-api-key"
```

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/observability`
*   **コミットメッセージ**: `feat: Datadogによる可観測性の実装 (Lambda & Step Functions)`
