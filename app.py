#!/usr/bin/env python3

import aws_cdk as cdk

from pipeline_stack import PipelineStack
from serverless_trip_saga_stack import ServerlessTripSagaStack

app = cdk.App()
ServerlessTripSagaStack(
    app,
    "ServerlessTripSagaStack",
)

PipelineStack(app, "PipelineStack")

app.synth()
