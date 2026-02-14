from aws_cdk import (
    CfnStack,
    RemovalPolicy,
    SecretValue,
)
from aws_cdk import (
    aws_lambda as _lambda,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_stepfunctions as sfn,
)
from constructs import Construct
from datadog_cdk_constructs_v2 import DatadogLambda, DatadogStepFunctions


class Observability(Construct):
    """可観測性を管理する Construct (Datadog版)

    SSM Parameter Store の API Key を起点に、以下を自己完結的に構築する:
    1. Secrets Manager Secret (SSM SecureString から動的参照)
    2. Datadog Forwarder (公式 CloudFormation テンプレートを CfnStack でデプロイ)
    3. Lambda / Step Functions の Datadog 計装
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        functions: list[_lambda.Function],
        state_machine: sfn.StateMachine,
        datadog_api_key_ssm_parameter_name: str = (
            "/serverless-trip-saga/datadog-api-key"
        ),
        service_name: str = "serverless-trip-saga",
        env: str = "dev",
    ) -> None:
        super().__init__(scope, id)

        # 1. Secrets Manager Secret の作成
        api_key_secret = secretsmanager.Secret(
            self,
            "DatadogApiKeySecret",
            secret_string_value=SecretValue.ssm_secure(
                datadog_api_key_ssm_parameter_name
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # 2. Datadog Forwarder のデプロイ (Nested Stack)
        forwarder_stack = CfnStack(
            self,
            "DatadogForwarder",
            template_url="https://datadog-cloudformation-template.s3.amazonaws.com/aws/forwarder/latest.yaml",
            parameters={
                "DdApiKeySecretArn": api_key_secret.secret_arn,
                "DdSite": "datadoghq.com",
                "FunctionName": f"{service_name}-datadog-forwarder",
            },
        )

        forwarder_arn = forwarder_stack.get_att(
            "Outputs.DatadogForwarderArn"
        ).to_string()

        # 3. Lambda Functions の計装
        datadog_lambda = DatadogLambda(
            self,
            "DatadogLambda",
            python_layer_version=122,
            extension_layer_version=92,
            api_key_secret_arn=api_key_secret.secret_arn,
            enable_datadog_tracing=True,
            enable_datadog_logs=True,
            capture_lambda_payload=True,
            site="datadoghq.com",
            service=service_name,
            env=env,
        )
        datadog_lambda.add_lambda_functions(functions)

        # 4. Step Functions の計装
        datadog_sfn = DatadogStepFunctions(
            self,
            "DatadogSfn",
            env=env,
            service=service_name,
            version="1.0.0",
            forwarder_arn=forwarder_arn,
        )
        datadog_sfn.add_state_machines([state_machine])
