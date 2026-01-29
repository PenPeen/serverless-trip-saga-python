from aws_cdk import Stack
from constructs import Construct

from infra.constructs import Database, Functions, Layers


class ServerlessTripSagaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Database Construct
        database = Database(self, "Database")

        # Layers Construct
        layers = Layers(self, "Layers")

        # Functions Construct
        Functions(
            self,
            "Functions",
            table=database.table,
            common_layer=layers.common_layer,
        )
