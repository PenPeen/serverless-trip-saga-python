from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct


class Api(Construct):
    """API Gateway Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        state_machine: sfn.StateMachine,
        get_trip: _lambda.Function,
        list_trips: _lambda.Function,
        origin_verify_secret: secretsmanager.ISecret,
    ) -> None:
        super().__init__(scope, id)

        self.rest_api = apigw.RestApi(
            self,
            "TripRestApi",
            rest_api_name="Trip Booking API",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_burst_limit=10,
                throttling_rate_limit=5,
            ),
        )

        # IAM Role: API Gateway -> Step Functions StartExecution
        apigw_role = iam.Role(
            self,
            "ApiGatewayStepFunctionsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
        )
        state_machine.grant_start_execution(apigw_role)

        # Lambda Authorizer: x-origin-verify ヘッダーで CloudFront 経由のみ許可
        authorizer_fn = _lambda.Function(
            self,
            "OriginVerifyAuthorizerFn",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="authorizer.handler.lambda_handler",
            code=_lambda.Code.from_asset("src"),
            environment={
                "ORIGIN_VERIFY_SECRET_ARN": origin_verify_secret.secret_arn,
            },
        )
        origin_verify_secret.grant_read(authorizer_fn)

        authorizer = apigw.RequestAuthorizer(
            self,
            "OriginVerifyAuthorizer",
            handler=authorizer_fn,
            identity_sources=[apigw.IdentitySource.header("x-origin-verify")],
            results_cache_ttl=Duration.seconds(300),
        )

        # POST /trips -> Step Functions (非同期)
        trips_resource = self.rest_api.root.add_resource("trips")

        sfn_integration = apigw.AwsIntegration(
            service="states",
            action="StartExecution",
            integration_http_method="POST",
            options=apigw.IntegrationOptions(
                credentials_role=apigw_role,
                request_templates={
                    "application/json": (
                        '#set($input = $input.json("$"))\n'
                        "{\n"
                        f'  "stateMachineArn": "{state_machine.state_machine_arn}",\n'
                        '  "input": "$util.escapeJavaScript($input)"\n'
                        "}"
                    ),
                },
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": (
                                '#set($result = $input.path("$"))\n'
                                "{\n"
                                '  "executionArn": "$result.executionArn",\n'
                                '  "startDate": "$result.startDate"\n'
                                "}"
                            ),
                        },
                    ),
                    apigw.IntegrationResponse(
                        status_code="400",
                        selection_pattern="4\\d{2}",
                    ),
                    apigw.IntegrationResponse(
                        status_code="500",
                        selection_pattern="5\\d{2}",
                    ),
                ],
            ),
        )

        trips_resource.add_method(
            "POST",
            sfn_integration,
            method_responses=[
                apigw.MethodResponse(status_code="200"),
                apigw.MethodResponse(status_code="400"),
                apigw.MethodResponse(status_code="500"),
            ],
            authorizer=authorizer,
        )

        # GET /trips -> Lambda (list_trips)
        trips_resource.add_method(
            "GET",
            apigw.LambdaIntegration(list_trips),
            authorizer=authorizer,
        )

        # GET /trips/{trip_id} -> Lambda (get_trip)
        trip_resource = trips_resource.add_resource("{trip_id}")
        trip_resource.add_method(
            "GET",
            apigw.LambdaIntegration(get_trip),
            authorizer=authorizer,
        )
