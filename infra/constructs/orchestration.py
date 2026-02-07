from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from infra.constructs.functions import Functions


class Orchestration(Construct):
    """Step Functions ステートマシーン"""

    def __init__(self, scope: Construct, id: str, functions: Functions):
        super().__init__(scope, id)

        reserve_flight_task = tasks.LambdaInvoke(
            self,
            "ReserveFlight",
            lambda_function=functions.flight_reserve,
            retry_on_service_exceptions=True,
            result_path="$.results.flight",
        )

        reserve_hotel_task = tasks.LambdaInvoke(
            self,
            "ReserveHotel",
            lambda_function=functions.hotel_reserve,
            retry_on_service_exceptions=True,
            result_path="$.results.hotel",
        )

        process_payment_task = tasks.LambdaInvoke(
            self,
            "ProcessPayment",
            lambda_function=functions.payment_process,
            retry_on_service_exceptions=True,
            result_path="$.results.payment",
        )

        definition = reserve_flight_task.next(reserve_hotel_task).next(
            process_payment_task.next(sfn.Succeed(self, "BookingSucceeded"))
        )

        self.state_machine = sfn.StateMachine(
            self,
            "TripBookingStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
        )
