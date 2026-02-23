from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_lambda_event_sources as event_sources
from constructs import Construct


class Functions(Construct):
    """Lambda 関数を管理する Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        table: dynamodb.Table,
        search_table: dynamodb.Table,
        common_layer: _lambda.LayerVersion,
    ) -> None:
        super().__init__(scope, id)

        self.flight_reserve = self._create_function(
            "FlightReserveLambda",
            "services.flight.handlers.reserve.lambda_handler",
            "flight-service",
            table,
            common_layer,
        )

        self.flight_cancel = self._create_function(
            "FlightCancelLambda",
            "services.flight.handlers.cancel.lambda_handler",
            "flight-service",
            table,
            common_layer,
        )

        self.hotel_reserve = self._create_function(
            "HotelReserveLambda",
            "services.hotel.handlers.reserve.lambda_handler",
            "hotel-service",
            table,
            common_layer,
        )

        self.hotel_cancel = self._create_function(
            "HotelCancelLambda",
            "services.hotel.handlers.cancel.lambda_handler",
            "hotel-service",
            table,
            common_layer,
        )

        self.payment_process = self._create_function(
            "PaymentProcessLambda",
            "services.payment.handlers.process.lambda_handler",
            "payment-service",
            table,
            common_layer,
        )

        self.payment_refund = self._create_function(
            "PaymentRefundLambda",
            "services.payment.handlers.refund.lambda_handler",
            "payment-service",
            table,
            common_layer,
        )

        for fn in [
            self.flight_reserve,
            self.flight_cancel,
            self.hotel_reserve,
            self.hotel_cancel,
            self.payment_process,
            self.payment_refund,
        ]:
            table.grant_read_write_data(fn)

        self.get_trip = self._create_function(
            "GetTripLambda",
            "services.trip.handlers.get_trip.lambda_handler",
            "trip-service",
            table,
            common_layer,
        )

        self.list_trips = self._create_function(
            "ListTripsLambda",
            "services.trip.handlers.list_trips.lambda_handler",
            "trip-service",
            table,
            common_layer,
        )

        table.grant_read_data(self.get_trip)
        table.grant_read_data(self.list_trips)

        self.stream_consumer = self._create_function(
            "StreamConsumer",
            "services.trip.handlers.stream_consumer.lambda_handler",
            "trip-service",
            table,
            common_layer,
        )
        self.stream_consumer.add_environment(
            "SEARCH_TABLE_NAME", search_table.table_name
        )
        search_table.grant_read_write_data(self.stream_consumer)
        self.stream_consumer.add_event_source(
            event_sources.DynamoEventSource(
                table,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=10,
                bisect_batch_on_error=True,
                retry_attempts=3,
            )
        )

        self.search_trips = self._create_function(
            "SearchTrips",
            "services.trip.handlers.search_trips.lambda_handler",
            "trip-service",
            table,
            common_layer,
        )
        self.search_trips.add_environment("SEARCH_TABLE_NAME", search_table.table_name)
        search_table.grant_read_data(self.search_trips)

        self.all_functions = [
            self.flight_reserve,
            self.flight_cancel,
            self.hotel_reserve,
            self.hotel_cancel,
            self.payment_process,
            self.payment_refund,
            self.get_trip,
            self.list_trips,
            self.stream_consumer,
            self.search_trips,
        ]

    def _create_function(
        self,
        id: str,
        handler: str,
        service_name: str,
        table: dynamodb.Table,
        common_layer: _lambda.LayerVersion,
    ) -> _lambda.Function:
        return _lambda.Function(
            self,
            id,
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler=handler,
            code=_lambda.Code.from_asset("src"),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": service_name,
            },
        )
