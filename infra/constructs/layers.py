import logging
import subprocess
from pathlib import Path

import jsii
from aws_cdk import BundlingOptions, ILocalBundling
from aws_cdk import aws_lambda as _lambda
from constructs import Construct

logger = logging.getLogger(__name__)


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
            logger.warning("requirements.txt not found: %s", requirements_path)
            return False

        # uvを優先し、なければpipを使用
        if self._try_uv_install(requirements_path, target_dir):
            return True

        if self._try_pip_install(requirements_path, target_dir):
            return True

        logger.warning("Local bundling failed, falling back to Docker")
        return False

    def _try_uv_install(self, requirements_path: Path, target_dir: Path) -> bool:
        """uvでインストールを試行する。"""
        try:
            logger.info("Trying local bundling with uv...")
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
            logger.info("Local bundling with uv succeeded")
            return True
        except FileNotFoundError:
            logger.debug("uv not found, trying pip")
            return False
        except subprocess.CalledProcessError as e:
            logger.debug("uv install failed: %s", e)
            return False

    def _try_pip_install(self, requirements_path: Path, target_dir: Path) -> bool:
        """pipでインストールを試行する。"""
        try:
            logger.info("Trying local bundling with pip...")
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
            logger.info("Local bundling with pip succeeded")
            return True
        except FileNotFoundError:
            logger.debug("pip not found")
            return False
        except subprocess.CalledProcessError as e:
            logger.debug("pip install failed: %s", e)
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
