from typing import Dict, Optional

import requests


class ReverseGeocoder:
    """
    逆ジオコーダー

    - Google Maps Geocoding APIを使用し、座標から住所文字列を取得する。
    - 同一の量子化済み座標については結果をキャッシュしてAPI呼び出しを削減する。
    - APIキーが空の場合は、座標文字列（"lat,lon"）をそのまま返す。

    Attributes:
        api_key (str): Google Maps APIキー（空文字ならAPI呼び出しを行わない）
        language (str): 応答言語コード（デフォルト: "ja"）
        timeout (float): HTTPリクエストのタイムアウト秒数
        endpoint (str): Geocoding APIのエンドポイントURL
        _session (requests.Session): HTTPセッションオブジェクト（外部再利用可）
        _cache (Dict[str, str]): 座標文字列→住所文字列のキャッシュ辞書
    """

    def __init__(
        self,
        api_key: str,
        language: str = "ja",
        timeout: float = 5.0,
        session: Optional[requests.Session] = None,
        endpoint: str = "https://maps.googleapis.com/maps/api/geocode/json",
    ) -> None:
        self.api_key = api_key
        self.language = language
        self.timeout = timeout
        self.endpoint = endpoint
        self._session = session or requests.Session()
        self._cache: Dict[str, str] = {}

    def lookup(self, lat_q: float, lon_q: float) -> str:
        """
        逆ジオコード

        量子化済み座標を受け取り、住所を返す。

        キャッシュに存在する場合は再利用し、
        APIキーが設定されていない場合は "lat,lon" の文字列を返す。

        Args:
            lat_q (float): 緯度（量子化後）[deg]
            lon_q (float): 経度（量子化後）[deg]

        Returns:
            str: 住所文字列または "lat,lon" 形式の座標文字列
        """
        key = f"{lat_q:.5f},{lon_q:.5f}"
        if key in self._cache:
            return self._cache[key]

        # APIキー未指定 → 座標をそのまま返す
        if not self.api_key:
            self._cache[key] = key
            return key

        addr = self._call_google_api(lat_q, lon_q)
        self._cache[key] = addr
        return addr

    # ---- internal --------------------------------------------------------
    def _call_google_api(self, lat: float, lon: float) -> str:
        """
        エンドポイント呼び出し

        Google Maps Geocoding APIを呼び出して住所を取得する。

        失敗時（ネットワーク・JSON・ステータス異常など）は
        座標文字列 "lat,lon" を返す。

        Args:
            lat (float): 緯度 [deg]
            lon (float): 経度 [deg]

        Returns:
            str: formatted_address または "lat, lon" 文字列
        """
        params = {
            "latlng": f"{lat},{lon}",
            "key": self.api_key,
            "language": self.language,
        }
        try:
            resp = self._session.get(self.endpoint, params=params, timeout=self.timeout)
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                return data["results"][0]["formatted_address"]
        except Exception:
            pass  # ネットワークやJSONエラー時はそのままフォールバック

        return f"{lat:.5f}, {lon:.5f}"
