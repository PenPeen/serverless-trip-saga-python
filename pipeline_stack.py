from aws_cdk import (
    Stack,
    Stage,
    pipelines,
)
from aws_cdk import (
    aws_codestarconnections as codestarconnections,
)
from constructs import Construct

from serverless_trip_saga_stack import ServerlessTripSagaStack


class ApplicationStage(Stage):
    """アプリケーションスタックをグループ化したステージ"""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ServerlessTripSagaStack(self, "ServerlessTripSaga")


class PipelineStack(Stack):
    """CI/CD パイプラインを定義するスタック"""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # GitHub との接続を作成（初回デプロイ後に手動認証が必要）
        github_connection = codestarconnections.CfnConnection(
            self,
            "GitHubConnection",
            connection_name="serverless-trip-saga-github",
            provider_type="GitHub",
        )

        pipeline = pipelines.CodePipeline(
            self,
            "Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.connection(
                    "PenPeen/serverless-trip-saga-python",
                    "main",
                    connection_arn=github_connection.attr_connection_arn,
                ),
                install_commands=[
                    "npm install -g aws-cdk",
                    "pip install uv",
                ],
                commands=[
                    "uv sync --frozen",
                    "uv run pytest tests/unit",
                    "uv run cdk synth",
                ],
            ),
        )

        pipeline.add_stage(
            ApplicationStage(self, "Prod"),
            pre=[
                pipelines.ManualApprovalStep(
                    "PromoteToProd",
                    comment="本番環境へデプロイします。Synth・テスト結果を確認のうえ承認してください。",
                )
            ],
        )
