import json
from typing import Any, Dict

from hook.store.store_encoder import StoreEncoder


class StoreKeeper:
    """
    設定ファイル管理
    """

    @staticmethod
    def read(file_path: str) -> Dict[str, Any]:
        """
        読み込み

        日付項目は使用しないため、日付変換しない

        Params:
            file_path(str): 設定ファイルパス

        Returns:
            dict: 設定ファイル内容
        """
        with open(file_path, "r", encoding="utf-8") as json_file:
            return json.load(json_file)

    @staticmethod
    def write(file_path: str, data: Dict[str, Any], indent: int = 2) -> None:
        """
        書き込み

        日付項目も出力

        Params:
            file_path(str): 設定ファイルパス
            data(dict): 設定ファイル内容
            indent(int): JSONインデント
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=StoreEncoder, ensure_ascii=False, indent=indent)
