from aws_cdk import Stack
from cdk_nag import NagSuppressions
from constructs import Construct

from infra.constructs import (
    Api,
    Auth,
    Cdn,
    Database,
    Deployment,
    Functions,
    Layers,
    Observability,
    Orchestration,
)


class ServerlessTripSagaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        auth = Auth(self, "Auth")
        database = Database(self, "Database")
        layers = Layers(self, "Layers")

        fns = Functions(
            self,
            "Functions",
            table=database.table,
            search_table=database.search_table,
            common_layer=layers.common_layer,
        )

        deployment = Deployment(
            self,
            "Deployment",
            flight_reserve=fns.flight_reserve,
            hotel_reserve=fns.hotel_reserve,
            payment_process=fns.payment_process,
        )

        orchestration = Orchestration(
            self,
            "Orchestration",
            flight_reserve=deployment.flight_reserve_alias,
            flight_cancel=fns.flight_cancel,
            hotel_reserve=deployment.hotel_reserve_alias,
            hotel_cancel=fns.hotel_cancel,
            payment_process=deployment.payment_process_alias,
        )

        api = Api(
            self,
            "Api",
            state_machine=orchestration.state_machine,
            get_trip=fns.get_trip,
            list_trips=fns.list_trips,
            search_trips=fns.search_trips,
            user_pool=auth.user_pool,
        )

        Cdn(
            self,
            "Cdn",
            rest_api=api.rest_api,
        )

        Observability(
            self,
            "Observability",
            functions=fns.all_functions,
            state_machine=orchestration.state_machine,
        )

        # cdk-nag: ハンズオン用途の意図的ルール逸脱を抑制
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Hands-on app uses AWS managed policies for simplicity",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Hands-on app uses wildcard IAM policies for simplicity",
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Runtime version fixed for hands-on stability",
                },
                {
                    "id": "AwsSolutions-SF1",
                    "reason": "Step Functions CloudWatch logging not required",
                },
                {
                    "id": "AwsSolutions-SF2",
                    "reason": "Step Functions X-Ray tracing not required for hands-on",
                },
                {
                    "id": "AwsSolutions-DDB3",
                    "reason": "DynamoDB PITR not required for hands-on",
                },
                {
                    "id": "AwsSolutions-APIG2",
                    "reason": "API Gateway access logging not required for hands-on",
                },
                {
                    "id": "AwsSolutions-COG4",
                    "reason": "Cognito authorizer handled at construct level",
                },
                {
                    "id": "AwsSolutions-CFR4",
                    "reason": "CloudFront TLS policy is hands-on default",
                },
            ],
        )
