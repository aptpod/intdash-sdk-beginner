import os

from src.lambda_function import lambda_handler


def test_200_processed() -> None:
    try:
        os.environ["API_URL"] = "https://example.intdash.jp"
        os.environ["API_TOKEN"] = "<YOUR_API_TOKEN>"
        os.environ["FETCH_SIZE"] = "100"
        os.environ["ORIGIN_LAT"] = "35.6878973"
        os.environ["ORIGIN_LON"] = "139.7170926"
        os.environ["SLACK_URL"] = "<YOUR_SLACK_WEBHOOK_URL>"

        event = {
            "project_uuid": "00000000-0000-0000-0000-000000000000",
            "measurement_uuid": "1a14f158-2a0c-44c7-ace1-e0d21ecc93e9",
            "delivery_uuid": "<DUMMY_DELIVERY_UUID>",
            "hook_uuid": "<DUMMY_HOOK_UUID>",
            "resource_type": "measurement",
            "action": "completed",
            "occurred_at": "<DUMMY_OCCURRED_AT>",
        }
        context = None

        result = lambda_handler(event, context)
        assert result["statusCode"] == 200
        assert result["body"] == "Processing completed successfully."
    except Exception as e:
        print(f"Error during test: {e}")
        raise
