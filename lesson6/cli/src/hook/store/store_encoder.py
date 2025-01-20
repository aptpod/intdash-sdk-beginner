import json
from datetime import datetime
from typing import Any


class StoreEncoder(json.JSONEncoder):
    """
    設定エンコーダー
    """

    def default(self, obj: Any) -> Any:
        """
        エンコード
        日付項目のエンコード処理

        Params:
            obj(Any): 対象オブジェクト

        """
        if isinstance(obj, datetime):
            iso_str = obj.isoformat()
            if obj.microsecond:
                nano_str = "{:09d}".format(obj.microsecond * 1000)
                iso_str = iso_str.replace(f".{obj.microsecond:06d}", f".{nano_str}")
            return iso_str
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return super().default(obj)
