from aws_cdk import Stack
from constructs import Construct

from infra.constructs import Database, Layers


class ServerlessTripSagaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Database(self, "Database")
        Layers(self, "Layers")
