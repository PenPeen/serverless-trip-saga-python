from aws_cdk import (
    Aws,
)
from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk import (
    aws_cloudfront as cloudfront,
)
from aws_cdk import (
    aws_cloudfront_origins as origins,
)
from aws_cdk import (
    aws_iam as iam,
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

        # OAC (Origin Access Control) for API Gateway — L1 Construct を使用
        # API Gateway 用の L2 OAC は CDK に存在しないため CfnOriginAccessControl を使用
        oac = cloudfront.CfnOriginAccessControl(
            self,
            "OAC",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name="TripApiGatewayOAC",
                origin_access_control_origin_type="apigateway",
                signing_behavior="always",
                signing_protocol="sigv4",
            ),
        )

        # API Gateway をオリジンとして設定
        origin = origins.RestApiOrigin(rest_api)

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

        # OAC を Distribution の Origin に紐付け（L1 Override）
        cfn_distribution = self.distribution.node.default_child
        cfn_distribution.add_property_override(
            "DistributionConfig.Origins.0.OriginAccessControlId",
            oac.attr_id,
        )

        # API Gateway リソースポリシー: CloudFront 経由のみ許可
        # 注意: rest_api.arn_for_execute_api() は Ref: RestApiId を含むため
        #       RestApi の Policy プロパティ内で使うと自己参照の循環依存が発生する。
        #       回避策として REST API ID 部分を * に置き換えた ARN を使用する。
        #       OAC の SigV4 署名が真正性を保証する
        rest_api.add_to_resource_policy(
            iam.PolicyStatement(
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["execute-api:Invoke"],
                resources=[
                    f"arn:{Aws.PARTITION}:execute-api:{Aws.REGION}:{Aws.ACCOUNT_ID}:*/*/*/*"
                ],
                conditions={"StringEquals": {"aws:SourceAccount": Aws.ACCOUNT_ID}},
            )
        )
