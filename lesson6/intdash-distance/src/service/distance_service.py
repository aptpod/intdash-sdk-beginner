import logging

from calculator.distance_calculator import DistanceCalculator
from notifier.notifier import Notifier
from reader.measurement_reader import MeasurementReader
from writer.measurement_writer import MeasurementWriter


class DistanceService:
    """
    距離算出サービス

    Attribute:
        reader (MeasurementReader): 計測取得
        calculator (DistanceCalculator): 距離算出
        writer (MeasurementWriter): 新規計測作成
        fetch_size (int): フェッチ件数
        notifier (Notifier): Slack通知
    """

    def __init__(
        self,
        reader: MeasurementReader,
        calculator: DistanceCalculator,
        writer: MeasurementWriter,
        fetch_size: int,
        notifier: Notifier,
    ) -> None:
        self.reader = reader
        self.caliculator = calculator
        self.writer = writer
        self.fetch_size = fetch_size
        self.notifier = notifier

    def process(self) -> None:
        """
        処理

        - 計測取得
        - データポイント取得
          - ”1/gnss_coordinates”を取得
          - フェッチ件数ごとに取得
        - 距離算出
        - 計測データ作成
          - 計測作成
          - シーケンス作成
          - チャンク送信
          - 計測削除（GPSデータなし）
          - 計測完了
        - Slack通知
        """
        # 計測取得
        measurement_src = self.reader.get_measurement()
        logging.info(f"Got measurement: {measurement_src.uuid}")

        # 計測作成
        measurement_dst = self.writer.create_measurement(measurement_src)
        logging.info(f"Created measurement: {measurement_dst.uuid}")

        sequence_uuid = None
        count = 0
        while True:
            # データポイント取得
            distances: list = []
            datapoints = self.reader.get_coordinates(self.fetch_size)
            if not datapoints:
                break
            logging.info(f"Fetched datapoints: {len(datapoints)}")

            # 距離算出
            for point_time, coord in datapoints:
                distance = self.caliculator.calculate(coord)
                distances.append((point_time, distance))
            count = count + len(distances)

            # シーケンス作成
            sequence = self.writer.replace_measurement_sequence(
                sequence_uuid if sequence_uuid else None,
                count,
            )
            logging.info(f"Replaced measurement sequence: {sequence.uuid}")

            # チャンク送信
            sequence_uuid = sequence.uuid
            results = self.writer.send_chunks(sequence.uuid, distances)
            for result in results.items:
                logging.info(
                    f"Sent sequence chunk: sequence number {result.sequence_number}, result: {result.result}"
                )

        # 計測削除（GPSデータなし）
        if not count:
            self.writer.delete_measurement()
            logging.info(f"Deleted measurement: {measurement_dst.uuid}")
            return

        # 計測完了
        self.writer.complete_measurement()
        logging.info(f"Completed measurement: {measurement_dst.uuid}")

        # Slack通知
        self.notifier.notify(measurement_dst.uuid)
        logging.info(f"Notified: {measurement_dst.uuid}")
