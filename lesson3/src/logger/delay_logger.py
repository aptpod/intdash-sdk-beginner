import logging
from typing import Optional

import iscp


class DelayLogger:
    """
    遅延ロガー

    メタデータの基準時刻とデータポイントの経過時間から絶対時刻を算出し、
    現在時刻との差を遅延としてログ出力（ミリ秒単位）
    精度はエッジと本処理のNTP誤差に依存

    Attributes:
        time_offset (int): タイムゾーン時差
        basetime (iscp.DateTime): 基準時刻（最優先）
        priority (int): 優先度
    """

    def __init__(self, time_offset: int) -> None:
        self.time_offset = time_offset
        self.basetime: Optional[iscp.DateTime] = None
        self.priority: Optional[int] = None

    def set_basetime(
        self,
        basetime: iscp.DateTime,
        priority: int,
    ) -> None:
        """
        基準時刻設定

        最も優先度の高い基準時刻を保持

        Args:
            basetime (iscp.DateTime): 基準時刻（最優先）
            priority (int): 優先度
        """
        if not self.basetime or not self.priority or priority >= self.priority:
            self.basetime = basetime
            self.priority = priority

    def log(self, elapsed_time: int) -> None:
        """
        ログ出力

        Args:
            elapsed_time (int): 経過時間
        """
        if not self.basetime:
            return
        current_time = iscp.DateTime.utcnow()
        absolute_time_unix_nano = self.basetime.unix_nano() + elapsed_time
        absolute_time = iscp.DateTime.from_unix_nano(absolute_time_unix_nano)
        delay = (current_time.unix_nano() - absolute_time.unix_nano()) / 1_000_000
        logging.info(
            f"Data point Absolute time: {absolute_time} Current time: {current_time} Delay: {delay:.3f} ms"
        )
