from aws_lambda_powertools import Logger


def get_logger(service_name: str) -> Logger:
    return Logger(service=service_name)
