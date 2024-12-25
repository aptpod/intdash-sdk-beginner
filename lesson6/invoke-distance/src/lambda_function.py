import base64
import hashlib
import hmac
import json
import logging
import os
import sys
from typing import Any, Dict

import boto3

# ログ設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def verify_hmac(secret: str, payload: str, received: str) -> bool:
    """
    HMAC検証

    Args:
        secret (str): シークレットキー
        payload (str): ペイロード
        received (str): 受信したHMAC

    Returns:
        bool: 検証結果（True: 成功, False: 失敗）
    """
    hmac_obj = hmac.new(secret.encode(), payload.encode(), hashlib.sha256)
    computed = base64.b64encode(hmac_obj.digest()).decode()
    return hmac.compare_digest(computed, received)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    エントリポイント

    - HMAC検証
    - リソースタイプとアクションの判定
        計測完了以外は無視
    - 距離算出Lambdaを非同期起動

    Args:
        event (dict): イベント
        context (LambdaContext): コンテキスト

    Returns:
        dict: APIレスポンス
    """
    secret_key = os.getenv("SECRET_KEY", "")
    lambda_client = boto3.client("lambda")

    headers = event.get("headers", {})
    body = event.get("body", "{}")
    logger.info(f"Received event: {event}")

    body_dict = json.loads(body)
    payload = json.dumps(body_dict, separators=(",", ":"))

    # HMAC検証
    signature = headers.get("x-intdash-signature-256", "")
    if not verify_hmac(secret_key, payload, signature):
        logger.warning("HMAC Verification Failed.")
        return {
            "statusCode": 401,
            "body": json.dumps({"message": "HMAC verification failed"}),
        }

    # リソースタイプとアクションの判定
    resource_type = body_dict.get("resource_type")
    action = body_dict.get("action")
    if resource_type != "measurement" or action != "completed":
        logger.info(f"Ignored: resource_type={resource_type}, action={action}")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Resource_type or action ignored"}),
        }

    # 距離算出Lambdaを非同期起動
    try:
        response = lambda_client.invoke(
            FunctionName="intdash-distance",
            InvocationType="Event",
            Payload=json.dumps(body_dict),
        )
        logger.info(f"Distance Lambda invoked successfully: {response}")
    except Exception as e:
        logger.error(f"Failed to invoke Distance Lambda: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Failed to invoke Distance Lambda"}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Webhook received and Distance Lambda invoked"}),
    }
