from aws_cdk import Stack
from constructs import Construct

from infra.constructs import (
    Api,
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

        database = Database(self, "Database")
        layers = Layers(self, "Layers")

        fns = Functions(
            self,
            "Functions",
            table=database.table,
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

        Api(
            self,
            "Api",
            state_machine=orchestration.state_machine,
            get_trip=fns.get_trip,
            list_trips=fns.list_trips,
        )

        Observability(
            self,
            "Observability",
            functions=fns.all_functions,
            state_machine=orchestration.state_machine,
        )
