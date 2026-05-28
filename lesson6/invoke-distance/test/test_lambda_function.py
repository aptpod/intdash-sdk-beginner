import os
from typing import Any
from unittest.mock import patch

from src.lambda_function import lambda_handler


@patch("src.lambda_function.boto3.client")
def test_200_invoked(mock_boto3_client: Any, monkeypatch: Any) -> None:
    os.environ["SECRET_KEY"] = "stringstringstringstringstringst"
    os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-1"

    mock_lambda_client = mock_boto3_client.return_value
    mock_lambda_client.invoke.return_value = {
        "StatusCode": 202,
        "Payload": None,
    }

    event = {
        "headers": {
            "x-intdash-signature-256": "xLDu+qI59GmQxQpCn0MjVwzIH9HY3SYkY2dF6kWLMrQ=",
        },
        "body": (
            "{"
            '"delivery_uuid":"d41cd3e1-7bf3-481e-bb68-1efeef5bd62a",'
            '"hook_uuid":"5b7ea816-0d3b-4df5-9104-01046ebecf51",'
            '"resource_type":"measurement",'
            '"action":"completed",'
            '"occurred_at":"2024-12-25T00:23:50.972454Z",'
            '"measurement_uuid":"1a14f158-2a0c-44c7-ace1-e0d21ecc93e9",'
            '"project_uuid":"00000000-0000-0000-0000-000000000000"'
            "}"
        ),
    }
    context = None

    result = lambda_handler(event, context)
    assert result["statusCode"] == 200
    assert "Webhook received and Distance Lambda invoked" in result["body"]
    mock_lambda_client.invoke.assert_called_once()
