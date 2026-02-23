from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from constructs import Construct


class Cdn(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        rest_api: apigw.RestApi,
    ) -> None:
        super().__init__(scope, id)

        # API Gateway をオリジンとして設定
        origin = origins.RestApiOrigin(rest_api)

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origin,
                # 全メソッド転送（POST 含む）
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                # ユーザー認証があるためキャッシュは無効化（安全策）
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            ),
            # HTTPS のみ
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
        )
