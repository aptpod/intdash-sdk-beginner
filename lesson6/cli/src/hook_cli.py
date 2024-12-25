import argparse
import json
import logging
import sys

from hook.hook.hook_manager import HookManager
from hook.store.store_encoder import StoreEncoder
from hook.store.store_manager import StoreKeeper

from intdash import exceptions
from intdash.api_client import ApiClient
from intdash.configuration import Configuration

# 定数
JSON_INDENT = 2

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def get_client(api_url: str, api_token: str) -> ApiClient:
    """
    APIクライアント取得

    Args:
        api_url: APIのURL
        api_token: APIトークン
    Returns:
        ApiClient: APIクライアント
    """
    configuration = Configuration(
        host=f"{api_url}/api", api_key={"IntdashToken": api_token}
    )
    client = ApiClient(configuration)
    return client


def main() -> None:
    """
    メイン

    Project Hookの各メソッドを実行する
        引数チェック
        メソッド実行
            list: 一覧
            export: 取得
            import: 登録
            delete: 削除
            test: テスト
                設定に登録されているurlにHook Requestを送信する
    """
    # 引数チェック
    parser = argparse.ArgumentParser(description="Webhook configuration CLI tool.")
    parser.add_argument("--api_url", required=True, help="URL of the API.")
    parser.add_argument("--api_token", required=True, help="API token.")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 各コマンド
    list_parser = subparsers.add_parser("list", help="List all webhook configurations.")
    list_parser.add_argument("--per_page", default="100", help="Max count per page.")

    export_parser = subparsers.add_parser(
        "export", help="Export a webhook configuration."
    )
    export_parser.add_argument(
        "--hook_uuid", required=True, help="UUID of the webhook to fetch."
    )
    export_parser.add_argument(
        "--dest_dir", help="Destination directory of JSON file configuration."
    )

    import_parser = subparsers.add_parser(
        "import", help="Import a webhook configuration."
    )
    import_parser.add_argument(
        "--src_path", required=True, help="Source JSON file with configuration."
    )
    import_parser.add_argument(
        "--hook_uuid",
        help="UUID of the webhook to update, or leave blank to create a new one.",
    )

    delete_parser = subparsers.add_parser(
        "delete", help="Delete a webhook configuration."
    )
    delete_parser.add_argument(
        "--hook_uuid", required=True, help="UUID of the webhook to delete."
    )

    test_parser = subparsers.add_parser("test", help="Test a webhook configuration.")
    test_parser.add_argument(
        "--hook_uuid", required=True, help="UUID of the webhook to test."
    )
    test_parser.add_argument(
        "--resource_type", default="measurement", help="Hooks Request resource type."
    )
    test_parser.add_argument(
        "--action", default="created", help="Hooks Request action."
    )
    args = parser.parse_args()

    # メソッド実行
    client = get_client(args.api_url, args.api_token)
    manager = HookManager(client, args.project_uuid)
    try:
        if args.command == "list":
            hooks = manager.list(int(args.per_page))
            logging.info(
                f"Listed Hooks count: {len(hooks)}\n{json.dumps(hooks, indent=JSON_INDENT, cls=StoreEncoder)}"
            )

        elif args.command == "export":
            hook_got = manager.get(args.hook_uuid)
            logging.info(f"Got Hook\n{hook_got}")
            if args.dest_dir:
                dest_path = f"{args.dest_dir}/{args.hook_uuid}.json"
                StoreKeeper.write(dest_path, hook_got.to_dict())
                logging.info(f"Exported config file dest_path:{dest_path}")

        elif args.command == "import":
            hook_src = StoreKeeper.read(args.src_path)
            hook_res = manager.save(hook_src, args.hook_uuid)
            logging.info(f"Imported Hook\n{hook_res}")

        elif args.command == "delete":
            manager.delete(args.hook_uuid)
            logging.info(f"Deleted Hook hook_uuid:{args.hook_uuid}")

        elif args.command == "test":
            delivery = manager.test(args.hook_uuid, args.resource_type, args.action)
            logging.info(f"Tested Hook\n{delivery}")

    except exceptions.ApiValueError as e:
        logging.error(f"API error:{e}")


if __name__ == "__main__":
    main()
