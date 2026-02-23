from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class Database(Construct):
    """DynamoDB Construct"""

    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        self.table = dynamodb.Table(
            self,
            "TripTable",
            partition_key=dynamodb.Attribute(
                name="PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(
                name="GSI1PK", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="GSI1SK", type=dynamodb.AttributeType.STRING
            ),
        )

        self.search_table = dynamodb.Table(
            self,
            "TripSearchTable",
            partition_key=dynamodb.Attribute(
                name="trip_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.search_table.add_global_secondary_index(
            index_name="flight_status-departure_time-index",
            partition_key=dynamodb.Attribute(
                name="flight_status",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="departure_time",
                type=dynamodb.AttributeType.STRING,
            ),
        )
