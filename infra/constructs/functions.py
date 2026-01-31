from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda

from constructs import Construct


class Functions(Construct):
    """Lambda 関数を管理する Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        table: dynamodb.Table,
        common_layer: _lambda.LayerVersion,
    ) -> None:
        super().__init__(scope, id)

        # ========================================================================
        # Flight Service Lambda
        # ========================================================================
        self.flight_reserve = _lambda.Function(
            self,
            "FlightReserveLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.flight.handlers.reserve.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "flight-service",
            },
        )

        self.flight_cancel = _lambda.Function(
            self,
            "FlightCancelLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.flight.handlers.cancel.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "flight-service",
            },
        )

        # ========================================================================
        # Hotel Service Lambda
        # ========================================================================
        self.hotel_reserve = _lambda.Function(
            self,
            "HotelReserveLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.hotel.handlers.reserve.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "hotel-service",
            },
        )

        self.hotel_cancel = _lambda.Function(
            self,
            "HotelCancelLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.hotel.handlers.cancel.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "hotel-service",
            },
        )

        # ========================================================================
        # Payment Service Lambda
        # ========================================================================
        self.payment_process = _lambda.Function(
            self,
            "PaymentProcessLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.payment.handlers.process.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "payment-service",
            },
        )

        self.payment_refund = _lambda.Function(
            self,
            "PaymentRefundLambda",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="services.payment.handlers.refund.lambda_handler",
            code=_lambda.Code.from_asset("."),
            layers=[common_layer],
            environment={
                "TABLE_NAME": table.table_name,
                "POWERTOOLS_SERVICE_NAME": "payment-service",
            },
        )

        # ========================================================================
        # DynamoDB への読み書き権限を付与
        # ========================================================================
        table.grant_read_write_data(self.flight_reserve)
        table.grant_read_write_data(self.flight_cancel)
        table.grant_read_write_data(self.hotel_reserve)
        table.grant_read_write_data(self.hotel_cancel)
        table.grant_read_write_data(self.payment_process)
        table.grant_read_write_data(self.payment_refund)
