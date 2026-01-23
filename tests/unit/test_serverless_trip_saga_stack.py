import aws_cdk as core
import aws_cdk.assertions as assertions

from serverless_trip_saga_stack import ServerlessTripSagaStack


def test_stack_created():
    app = core.App()
    stack = ServerlessTripSagaStack(app, "ServerlessTripSagaStack")
    template = assertions.Template.from_stack(stack)

    # Verify the stack is empty as currently defined
    template.resource_count_is("AWS::SQS::Queue", 0)
