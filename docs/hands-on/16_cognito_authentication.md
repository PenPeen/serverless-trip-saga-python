# ハンズオン 16: Cognito User Pools によるユーザー認証の導入

本セクションでは、API Gateway に Amazon Cognito User Pools を統合し、標準的なユーザー認証フローを実装します。
これまで使用していた独自の経路認証（`x-origin-verify`）を廃止し、AWS のベストプラクティスに基づいた **ID トークンによる認証** へと移行します。

## 1. アーキテクチャと目的

AWS のサーバーレス Web アプリケーションリファレンスアーキテクチャ（Figure 6）に基づき、以下の構成を実現します。

*   **Amazon Cognito User Pools**: ユーザーディレクトリの管理と JWT（JSON Web Token）の発行を行います。
*   **API Gateway**: クライアントから送信された `Authorization` ヘッダー内のトークンを検証し、有効なユーザーのみリクエストを許可します。
*   **CloudFront**: コンテンツ配信と API へのルーティングを行いますが、認証自体はバックエンド（API Gateway）に委譲します。

### 変更の概要

| 変更箇所 | 変更前 | 変更後 |
| :--- | :--- | :--- |
| **認証方式** | カスタム Lambda Authorizer (`x-origin-verify` ヘッダー検証) | **Cognito User Pools Authorizer** (`Authorization` トークン検証) |
| **セキュリティ** | 経路認証（CloudFront 経由のみ許可） | **ユーザー認証**（認証済みユーザーのみ許可・ゼロトラスト） |
| **構成ファイル** | `src/authorizer/handler.py` | 廃止（削除） |

---

## 2. 認証リソース (Cognito) の定義

まず、認証基盤となる Cognito User Pool を定義する新しいコンストラクトを作成します。

**ファイル作成**: `infra/constructs/auth.py`

```python
from aws_cdk import RemovalPolicy
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class Auth(Construct):
    """Authentication Construct using Cognito"""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        # 1. User Pool の作成
        self.user_pool = cognito.UserPool(
            self,
            "TripUserPool",
            user_pool_name="trip-user-pool",
            self_sign_up_enabled=True,  # ユーザー自身のサインアップを許可
            sign_in_aliases=cognito.SignInAliases(email=True),  # メールアドレスでログイン
            auto_verify=cognito.AutoVerifiedAttrs(email=True),  # メールアドレスを自動検証
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,  # ハンズオン用: スタック削除時に削除
        )

        # 2. App Client の作成 (Web アプリ用)
        self.user_pool_client = self.user_pool.add_client(
            "TripWebClient",
            user_pool_client_name="trip-web-client",
            generate_secret=False,  # SPA/Web アプリでは Secret は不要
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=True,  # ハンズオン用: ユーザー名・パスワードでの簡易認証を許可
            ),
        )
```

## 3. API Gateway への Authorizer 適用

次に、API Gateway の設定を修正し、作成した User Pool を Authorizer として設定します。同時に、既存の独自認証 (`OriginVerifyAuthorizer`) を削除します。

**修正対象**: `infra/constructs/api.py`

```python
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito  # 追加
# ... (他のインポート)

class Api(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        state_machine: sfn.StateMachine,
        get_trip: _lambda.Function,
        list_trips: _lambda.Function,
        search_trips: _lambda.Function,
        user_pool: cognito.IUserPool,  # 引数を追加 (origin_verify_secret は削除)
    ) -> None:
        super().__init__(scope, id)

        # ... (RestApi 定義は変更なし)

        # 【削除】 Lambda Authorizer 関連のコード (role, function, secret 権限など)
        # origin_verify_secret.grant_read(authorizer_fn) ... 等を削除

        # 【追加】 Cognito Authorizer の定義
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "TripCognitoAuthorizer",
            cognito_user_pools=[user_pool],
            authorizer_name="TripCognitoAuthorizer",
            identity_source="method.request.header.Authorization",  # ヘッダー指定
        )

        # ... (各メソッドへの authorizer 適用は変更なし。変数名 authorizer がそのまま使えます)
```

**修正対象**: `serverless_trip_saga_stack.py` (メインスタック)

`Api` コンストラクトの呼び出し元も修正が必要です。

```python
from infra.constructs.auth import Auth  # 追加

# ...

class ServerlessTripSagaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. Auth コンストラクトの初期化
        auth = Auth(self, "Auth")

        # ... (Database, Functions, Orchestration の定義)

        # 5. API Gateway (Auth を渡すように変更)
        api = Api(
            self,
            "Api",
            state_machine=orchestration.state_machine,
            get_trip=functions.get_trip,
            list_trips=functions.list_trips,
            search_trips=functions.search_trips,
            user_pool=auth.user_pool,  # 追加
            # origin_verify_secret=...  # 削除
        )
```

## 4. デプロイと動作確認

コードの修正が完了したら、デプロイを行います。

```bash
cdk deploy
```

デプロイ完了後、以下の手順で動作を確認します。

### 4.1 ユーザーの作成 (AWS CLI)

テスト用のユーザーを作成し、パスワードを設定します。

```bash
# User Pool ID と Client ID を取得 (マネジメントコンソールまたは出力から確認)
USER_POOL_ID="<OutputのUserPoolId>"
CLIENT_ID="<OutputのClientId>"
USERNAME="testuser@example.com"
PASSWORD="Password123!"

# ユーザー作成
aws cognito-idp sign-up \
  --client-id $CLIENT_ID \
  --username $USERNAME \
  --password $PASSWORD

# ユーザーの確認 (本来はメール認証だが、管理者権限で承認)
aws cognito-idp admin-confirm-sign-up \
  --user-pool-id $USER_POOL_ID \
  --username $USERNAME
```

### 4.2 認証トークンの取得

作成したユーザーでログインし、`IdToken` を取得します。ハンズオンでは簡易的に `USER_PASSWORD_AUTH` フローを使用します。

```bash
TOKEN=$(aws cognito-idp initiate-auth \
  --client-id $CLIENT_ID \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=$USERNAME,PASSWORD=$PASSWORD \
  --query 'AuthenticationResult.IdToken' \
  --output text)

echo "Token: $TOKEN"
```

### 4.3 API へのアクセス確認

取得したトークンを使って API を呼び出します。

```bash
API_URL="<OutputのApiUrl>/trips"

# 成功パターン (トークンあり)
curl -X GET "$API_URL" \
  -H "Authorization: $TOKEN"

# 失敗パターン (トークンなし)
curl -X GET "$API_URL" -I
# -> HTTP/1.1 401 Unauthorized が返ることを確認
```

---

## 発展: 経路認証について

本ハンズオンではユーザー認証への移行を行いましたが、セキュリティ要件として「CloudFront 経由のアクセスのみに制限したい」というケースも存在します。
その場合、AWS WAF (Web Application Firewall) を API Gateway に関連付け、CloudFront が付与するカスタムヘッダー (`x-origin-verify` 等) を持つリクエストのみを許可する Web ACL を設定するのがベストプラクティスです。
これにより、Authorizer はユーザー認証に専念し、WAF が経路制御を担当するという適切な役割分担が可能になります。
