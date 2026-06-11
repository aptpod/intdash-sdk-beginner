import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(slots=True)
class SrtSegment:
    """
    SRTセグメント


    Attributes:
        start (float): セグメント開始時刻（sec, basetime相対）
        end (float): セグメント終了時刻（sec, basetime相対, 開始 < 終了）
        line1 (str): 1行目のテキスト（高度・速度などの要約）
        line2 (Optional[str]): 2行目のテキスト（住所 or 緯度経度）
    """

    start: float
    end: float
    line1: str
    line2: Optional[str] = None


class Aggregator:
    """
    字幕生成

    GNSSなどの時系列データを集約し、SRT字幕用のセグメントを生成

    動作:
        - 高度・速度・位置・住所を統合してテキスト化する。
        - 表示内容（line1/line2）が変化した時点でSRTセグメントを確定する。
        - 高度（1Hz程度）のtickで `on_tick()` を呼び出す運用を想定。
        - `finalize()` で末尾の未出力セグメントを閉じる。

    Attributes:
        quant_m (float): 緯度経度の量子化グリッド間隔 [m]
        _alt (float): 最新の高度 [m]
        _has_alt (bool): 高度の有無フラグ
        _spd (float): 最新の速度 [km/h]
        _has_spd (bool): 速度の有無フラグ
        _lat_q (float): 量子化済み緯度 [deg]
        _lon_q (float): 量子化済み経度 [deg]
        _has_latlon (bool): 緯度経度の有無フラグ
        _last_cell (Optional[Tuple[float, float]]): 前回の量子化セル（lat_q, lon_q）
        _addr (str): 現在の住所（未設定時は空文字）
        _cur_l1 (str): 現在のSRTセグメント1行目テキスト
        _cur_l2 (Optional[str]): 現在のSRTセグメント2行目テキスト
        _seg_start (Optional[float]): 現在のSRTセグメント開始時刻 [sec]
    """

    def __init__(self, quant_m: float = 100.0) -> None:
        self.quant_m = float(quant_m)
        # 値 + 所有フラグ
        self._alt: float = 0.0
        self._has_alt: bool = False
        self._spd: float = 0.0
        self._has_spd: bool = False
        self._lat_q: float = 0.0
        self._lon_q: float = 0.0
        self._has_latlon: bool = False
        self._last_cell: Optional[Tuple[float, float]] = None
        self._addr: str = ""

        # セグメント状態
        self._cur_l1: str = ""
        self._cur_l2: Optional[str] = None
        self._seg_start: Optional[float] = None

    # ---- updates ---------------------------------------------------------
    def update_altitude(self, meters: float) -> None:
        """
        高度更新

        Args:
            meters (float): 高度 [m]
        """
        self._alt = float(meters)
        self._has_alt = True

    def update_speed(self, kmh: float) -> None:
        """
        速度更新

        Args:
            kmh (float): 速度 [km/h]
        """
        self._spd = float(kmh)
        self._has_spd = True

    def update_latlon(self, lat: float, lon: float) -> Tuple[bool, float, float]:
        """
        緯度経度更新

        移動距離を量子化（セル化）し、セルが変化した場合に True を返す。
        住所はリセットされる。

        Args:
            lat (float): 緯度 [deg]
            lon (float): 経度 [deg]

        Returns:
            Tuple[bool, float, float]:
                (セル変化フラグ, 量子化緯度, 量子化経度)
        """
        lat_q, lon_q = self._quantize(lat, lon, self.quant_m)
        self._lat_q, self._lon_q = lat_q, lon_q
        self._has_latlon = True
        changed = self._last_cell != (lat_q, lon_q)
        if changed:
            self._last_cell = (lat_q, lon_q)
            self._addr = ""
        return changed, lat_q, lon_q

    def update_address(self, address: str) -> None:
        """
        住所更新

        Args:
            address (str): 住所文字列
        """
        self._addr = address

    def on_tick(self, t: float) -> Optional[SrtSegment]:
        """
        字幕出力

        現在の状態をもとにSRTセグメントを更新する。
        表示内容に変化があった場合のみ新しいセグメントを返す。

        Args:
            t (float): 評価時刻（sec, basetime相対）

        Returns:
            Optional[SrtSegment]: 変化時に確定したセグメント、変化がなければNone
        """
        l1, l2 = self._compose_lines()
        if self._seg_start is None:
            # セグメント開始
            self._cur_l1, self._cur_l2 = l1, l2
            self._seg_start = float(t)
            return None

        if l1 != self._cur_l1 or l2 != self._cur_l2:
            seg = SrtSegment(self._seg_start, float(t), self._cur_l1, self._cur_l2)
            self._cur_l1, self._cur_l2 = l1, l2
            self._seg_start = float(t)
            return seg
        return None

    def finalize(self, t_end: float) -> Optional[SrtSegment]:
        """
        終了

        最後のセグメントを閉じて返す。

        Args:
            t_end (float): 計測終了時刻（sec, basetime相対）

        Returns:
            Optional[SrtSegment]: 最終セグメント、未開始ならNone
        """
        if self._seg_start is None:
            return None
        seg = SrtSegment(self._seg_start, float(t_end), self._cur_l1, self._cur_l2)
        self._seg_start = None
        self._cur_l1, self._cur_l2 = "", None
        return seg

    # ---- internal --------------------------------------------------------
    def _compose_lines(self) -> Tuple[str, Optional[str]]:
        """
        表示行生成

        現在の高度・速度・位置情報からSRT表示行を生成する。

        Returns:
            Tuple[str, Optional[str]]:
                (1行目テキスト, 2行目テキスト)
        """
        # 丸めて表示の揺れを抑制（任意: ここで統一）
        alt = round(self._alt, 1) if self._has_alt else 0.0
        spd = round(self._spd, 1) if self._has_spd else 0.0
        line1 = f"Altitude: {alt:.1f} m  Speed: {spd:.1f} km/h"
        if self._addr:
            line2: Optional[str] = self._addr
        elif self._has_latlon:
            line2 = f"Lat: {self._lat_q:.5f}  Lon: {self._lon_q:.5f}"
        else:
            line2 = None
        return line1, line2

    @staticmethod
    def _quantize(lat: float, lon: float, meters: float) -> Tuple[float, float]:
        """
        量子化

        緯度経度を指定メッシュ[m]で量子化する。

        Args:
            lat (float): 緯度 [deg]
            lon (float): 経度 [deg]
            meters (float): メッシュサイズ [m]

        Returns:
            Tuple[float, float]: (量子化後の緯度, 経度)
        """
        if meters <= 0:
            return float(lat), float(lon)
        m_per_deg_lat = 111_132.0
        m_per_deg_lon = 111_320.0 * max(1e-6, math.cos(math.radians(lat)))
        dlat = meters / m_per_deg_lat
        dlon = meters / m_per_deg_lon
        lat_q = round(lat / dlat) * dlat
        lon_q = round(lon / dlon) * dlon
        return float(lat_q), float(lon_q)
