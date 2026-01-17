from aws_cdk import (
    Stack,
)
from constructs import Construct
from infra.constructs import Database   # infra/constructs/__init__.py を load

class ServerlessTripSagaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        database = Database(self, "Database")
