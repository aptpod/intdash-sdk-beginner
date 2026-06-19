import logging

import iscp


class DelayLogger:
    """
    遅延ロガー

    メタデータの基準時刻とデータポイントの経過時間から絶対時刻を算出し、
    現在時刻との差を遅延としてログ出力（ミリ秒単位）
    精度はエッジと本処理のNTP誤差に依存

    Attributes:
        time_offset (int): タイムゾーン時差
        basetimes (dict): セッションごとの基準時刻と優先度
    """

    def __init__(self, time_offset: int) -> None:
        self.time_offset = time_offset
        self.basetimes: dict[str, tuple[iscp.DateTime, int]] = {}

    def set_basetime(
        self,
        session_id: str,
        basetime: iscp.DateTime,
        priority: int,
    ) -> None:
        """
        基準時刻設定

        最も優先度の高い基準時刻を保持

        Args:
            session_id (str): セッションID
            basetime (iscp.DateTime): 基準時刻
            priority (int): 優先度
        """
        current = self.basetimes.get(session_id)
        if current is None or priority >= current[1]:
            self.basetimes[session_id] = (basetime, priority)

    def log(self, session_id: str, elapsed_time: int) -> None:
        """
        ログ出力

        Args:
            session_id (str): セッションID
            elapsed_time (int): 経過時間
        """
        current = self.basetimes.get(session_id)
        if current is None:
            return
        basetime, _ = current
        current_time = iscp.DateTime.utcnow()
        absolute_time_unix_nano = basetime.unix_nano() + elapsed_time
        absolute_time = iscp.DateTime.from_unix_nano(absolute_time_unix_nano)
        delay = (current_time.unix_nano() - absolute_time.unix_nano()) / 1_000_000
        logging.info(
            f"Data point Absolute time: {absolute_time} Current time: {current_time} Delay: {delay:.3f} ms"
        )
