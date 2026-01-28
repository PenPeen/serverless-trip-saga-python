import subprocess
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, ILocalBundling
from aws_cdk import aws_lambda as _lambda

from constructs import Construct


@jsii.implements(ILocalBundling)
class PythonLocalBundling:
    """ローカル環境でpip installを実行するBundlingクラス"""

    def __init__(self, source_path: str) -> None:
        self.source_path = source_path

    def try_bundle(self, output_dir: str, options: BundlingOptions) -> bool:
        """ローカルでバンドリングを試行する。

        Args:
            output_dir: 出力先ディレクトリ
            options: BundlingOptions（未使用だが必須）

        Returns:
            True: バンドリング成功（Dockerをスキップ）
            False: バンドリング失敗（Dockerにフォールバック）
        """
        del options  # unused
        requirements_path = Path(self.source_path) / "requirements.txt"
        target_dir = Path(output_dir) / "python"

        if not requirements_path.exists():
            return False

        try:
            # uvを優先し、なければpipを使用
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "-r",
                    str(requirements_path),
                    "--target",
                    str(target_dir),
                    "--quiet",
                ],
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # uvがない場合はpipにフォールバック
            try:
                subprocess.run(
                    [
                        "pip",
                        "install",
                        "-r",
                        str(requirements_path),
                        "-t",
                        str(target_dir),
                        "--quiet",
                    ],
                    check=True,
                )
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                return False


class Layers(Construct):
    """Lambda Layers Construct"""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        # NOTE: self.common_layerに格納することで、
        # 他のConstructやStackから参照可能にしている
        layer_source_path = "layers/common_layer"

        self.common_layer = _lambda.LayerVersion(
            self,
            "CommonLayer",
            code=_lambda.Code.from_asset(
                layer_source_path,
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_14.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output/python",
                    ],
                    local=PythonLocalBundling(layer_source_path),
                ),
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_14],
            description="Common dependencies Library",
        )
