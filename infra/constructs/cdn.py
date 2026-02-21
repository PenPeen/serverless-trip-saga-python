from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class Cdn(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        rest_api: apigw.RestApi,
        origin_verify_secret: secretsmanager.ISecret,
    ) -> None:
        super().__init__(scope, id)

        # API Gateway をオリジンとして設定（カスタムヘッダーで認証）
        origin = origins.RestApiOrigin(
            rest_api,
            custom_headers={
                "x-origin-verify": origin_verify_secret.secret_value.unsafe_unwrap()
            },
        )

        self.distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origin,
                # 全メソッド転送（POST 含む）、キャッシュは GET/HEAD のみ
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            ),
            # HTTPS のみ
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
        )
