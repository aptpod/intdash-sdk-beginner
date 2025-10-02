from typing import Any, Dict, Optional

from intdash.api.webhook_service_project_webhook_api import (
    WebhookServiceProjectWebhookApi,
)
from intdash.api_client import ApiClient
from intdash.model.hook_project import HookProject
from intdash.model.hook_project_create_response import HookProjectCreateResponse


class HookManager:
    """
    Webhook管理

    Attributes:
        client (ApiClient): APIクライアント
        project_uuid (str): プロジェクトUUID
        api (WebhookServiceProjectWebhookApi): APIオブジェクト
    """

    def __init__(self, client: ApiClient, project_uuid: str) -> None:
        self.client = client
        self.project_uuid = project_uuid
        self.api = WebhookServiceProjectWebhookApi(client)

    def list(self, per_page: int) -> list:
        """
        一覧

        Args:
            per_page (int): ページ中カウント

        Returns:
            list: Webhook設定リスト
        """
        return self.api.list_project_webhooks(
            self.project_uuid, per_page=per_page
        ).items

    def get(self, hook_uuid: str) -> HookProject:
        """
        取得

        Args:
            hook_uuid (str): Webhook UUID

        Returns:
            dict: Webhook設定
        """
        return self.api.get_project_webhook(self.project_uuid, hook_uuid)

    def save(
        self, hook_src: Dict[str, Any], hook_uuid: Optional[str] = None
    ) -> HookProjectCreateResponse:
        """
        登録

        Args:
            hook_src (dict): Webhook設定
            hook_uuid (str): Webhook UUID

        Returns:
            dict: Webhook設定
        """
        if hook_uuid:
            hook = self.api.update_project_webhook(
                self.project_uuid, hook_uuid, hook_project_update_request=hook_src
            )
        else:
            hook = self.api.create_project_webhook(
                self.project_uuid, hook_project_create_request=hook_src
            )
        return hook

    def delete(self, hook_uuid: str) -> Any:
        """
        削除

        Args:
            hook_uuid (str): Webhook UUID
        """
        return self.api.delete_project_webhook(self.project_uuid, hook_uuid)

    def test(self, hook_uuid: str, resource_type: str, action: str) -> Any:
        """
        テスト

        Args:
            hook_uuid (str): Webhook UUID
            resource_type(str): リソースタイプ
            action(str): アクション
        """
        return self.api.test_project_webhook(
            self.project_uuid,
            hook_uuid,
            hook_test_request={"resource_type": resource_type, "action": action},
        )
