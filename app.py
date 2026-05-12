#!/usr/bin/env python3

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

from pipeline_stack import PipelineStack

app = cdk.App()

PipelineStack(app, "PipelineStack")

# cdk-nag: AwsSolutions ルールパックを適用（synth 時にチェック）
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

app.synth()
