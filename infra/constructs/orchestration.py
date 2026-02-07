from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from infra.constructs.functions import Functions


class Orchestration(Construct):
    """Step Functions ステートマシーン"""

    def __init__(self, scope: Construct, id: str, functions: Functions):
        super().__init__(scope, id)

        # フライト予約
        reserve_flight_task = tasks.LambdaInvoke(
            self,
            "ReserveFlight",
            lambda_function=functions.flight_reserve,
            retry_on_service_exceptions=True,
            result_path="$.results.flight",
        )

        # ホテル予約
        reserve_hotel_task = tasks.LambdaInvoke(
            self,
            "ReserveHotel",
            lambda_function=functions.hotel_reserve,
            retry_on_service_exceptions=True,
            result_path="$.results.hotel",
        )

        # 決済処理
        process_payment_task = tasks.LambdaInvoke(
            self,
            "ProcessPayment",
            lambda_function=functions.payment_process,
            retry_on_service_exceptions=True,
            result_path="$.results.payment",
        )

        # 補償タスク
        # NOTE: Step Functions では同じタスクを複数のチェーンで再利用できないため、
        # ロールバックチェーンごとに別のタスクインスタンスを作成する

        # Hotel の予約を取り消す
        cancel_hotel_from_payment = tasks.LambdaInvoke(
            self,
            "CancelHotelFromPayment",
            lambda_function=functions.hotel_cancel,
            retry_on_service_exceptions=True,
            result_path="$.results.hotel_cancel",
        )

        # Flight の予約を取り消す
        cancel_flight_from_payment = tasks.LambdaInvoke(
            self,
            "CancelFlightFromPayment",
            lambda_function=functions.flight_cancel,
            retry_on_service_exceptions=True,
            result_path="$.results.flight_cancel",
        )

        # Flight の予約を取り消す
        cancel_flight_from_hotel = tasks.LambdaInvoke(
            self,
            "CancelFlightFromHotel",
            lambda_function=functions.flight_cancel,
            retry_on_service_exceptions=True,
            result_path="$.results.flight_cancel",
        )

        # 失敗State
        saga_failed_from_payment = sfn.Fail(
            self, "SagaFailedFromPayment", error="SagaFailed"
        )
        saga_failed_from_hotel = sfn.Fail(
            self, "SagaFailedFromHotel", error="SagaFailed"
        )

        # Payment 失敗時（Hotel Cancel → Flight Cancel → Fail）
        rollback_from_payment = cancel_hotel_from_payment.next(
            cancel_flight_from_payment
        ).next(saga_failed_from_payment)

        # Hotel 失敗時（Flight Cancel → Fail）
        rollback_from_hotel = cancel_flight_from_hotel.next(saga_failed_from_hotel)

        # エラーハンドリング
        process_payment_task.add_catch(
            rollback_from_payment, result_path="$.error_info"
        )

        reserve_hotel_task.add_catch(rollback_from_hotel, result_path="$.error_info")

        # ステートマシン定義
        definition = reserve_flight_task.next(reserve_hotel_task).next(
            process_payment_task.next(sfn.Succeed(self, "BookingSucceeded"))
        )

        self.state_machine = sfn.StateMachine(
            self,
            "TripBookingStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
        )
