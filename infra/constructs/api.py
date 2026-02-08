from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
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

        self.http_api = apigwv2.HttpApi(
            self,
            "TripApi",
            api_name="Trip Booking API",
            create_default_stage=False,
        )

        apigwv2.HttpStage(
            self,
            "DefaultStage",
            http_api=self.http_api,
            auto_deploy=True,
            stage_name="$default",
            throttle=apigwv2.ThrottleSettings(
                burst_limit=10,
                rate_limit=5,
            ),
        )

        # POST /trips -> Step Functions (非同期)
        self.http_api.add_routes(
            path="/trips",
            methods=[apigwv2.HttpMethod.POST],
            integration=integrations.HttpStepFunctionsIntegration(
                "StartExecution",
                state_machine=state_machine,
            ),
        )

        # GET /trips -> Lambda (list_trips)
        self.http_api.add_routes(
            path="/trips",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "ListTripsIntegration",
                handler=list_trips,
            ),
        )

        # GET /trips/{trip_id} -> Lambda (get_trip)
        self.http_api.add_routes(
            path="/trips/{trip_id}",
            methods=[apigwv2.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "GetTripIntegration",
                handler=get_trip,
            ),
        )
