from aws_cdk import Duration
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_codedeploy as codedeploy
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class Deployment(Construct):
    """カナリアデプロイを管理する Construct"""

    def __init__(
        self,
        scope: Construct,
        id: str,
        flight_reserve: _lambda.Function,
        hotel_reserve: _lambda.Function,
        payment_process: _lambda.Function,
    ) -> None:
        super().__init__(scope, id)

        self.flight_reserve_alias = self._create_canary_deployment(
            "FlightReserve", flight_reserve
        )
        self.hotel_reserve_alias = self._create_canary_deployment(
            "HotelReserve", hotel_reserve
        )
        self.payment_process_alias = self._create_canary_deployment(
            "PaymentProcess", payment_process
        )

    def _create_canary_deployment(
        self,
        name: str,
        fn: _lambda.Function,
    ) -> _lambda.Alias:
        alias = _lambda.Alias(
            self,
            f"{name}Alias",
            alias_name="Prod",
            version=fn.current_version,
        )

        error_rate_alarm = cloudwatch.Alarm(
            self,
            f"{name}ErrorRateAlarm",
            metric=cloudwatch.MathExpression(
                expression="(errors / invocations) * 100",
                using_metrics={
                    "errors": fn.metric_errors(statistic="Sum"),
                    "invocations": fn.metric_invocations(statistic="Sum"),
                },
                label=f"{name} Error Rate %",
                period=Duration.minutes(1),
            ),
            threshold=5,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )

        codedeploy.LambdaDeploymentGroup(
            self,
            f"{name}DeploymentGroup",
            alias=alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10_PERCENT_5_MINUTES,
            alarms=[error_rate_alarm],
        )

        return alias
