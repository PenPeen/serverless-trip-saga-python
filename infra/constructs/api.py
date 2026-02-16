from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
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
    ) -> None:
        super().__init__(scope, id)

        self.rest_api = apigw.RestApi(
            self,
            "TripApi",
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
        )

        # GET /trips -> Lambda (list_trips)
        trips_resource.add_method("GET", apigw.LambdaIntegration(list_trips))

        # GET /trips/{trip_id} -> Lambda (get_trip)
        trip_resource = trips_resource.add_resource("{trip_id}")
        trip_resource.add_method("GET", apigw.LambdaIntegration(get_trip))
