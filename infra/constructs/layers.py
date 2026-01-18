from aws_cdk import BundlingOptions
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class Layers(Construct):
    """Lambda Layers Construct"""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        # NOTE: self.common_layerに格納することで、他のConstructやStackから参照可能にしている
        self.common_layer = _lambda.LayerVersion(
            self,
            "CommonLayer",
            code=_lambda.Code.from_asset(
                "layers/common_layer",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c", "pip install -r requirements.txt -t /asset-output/python"
                    ],
                ),
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Common dependencies Library")
