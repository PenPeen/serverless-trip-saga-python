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
            sign_in_aliases=cognito.SignInAliases(
                email=True
            ),  # メールアドレスでログイン
            auto_verify=cognito.AutoVerifiedAttrs(
                email=True
            ),  # メールアドレスを自動検証
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
                user_password=True,  # ハンズオン用: パスワード認証を許可
            ),
        )
