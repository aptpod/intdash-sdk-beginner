import logging

from lesson2.distance.src.calculator.distance_calculator import DistanceCalculator
from lesson2.distance.src.reader.measurement_reader import MeasurementReader
from lesson2.distance.src.writer.measurement_writer import MeasurementWriter


class DistanceService:
    """
    距離算出サービス

    Attribute:
        project_uuid (str): プロジェクトUUID
        meas_uuid (str): 元計測UUID
        reader (MeasurementReader): 計測取得
        calculator (DistanceCalculator): 距離算出
        writer (MeasurementWriter): 新規計測作成
        fetch_size (int): フェッチ件数
    """

    def __init__(
        self,
        project_uuid: str,
        meas_uuid: str,
        reader: MeasurementReader,
        calculator: DistanceCalculator,
        writer: MeasurementWriter,
        fetch_size: int,
    ) -> None:
        self.project_uuid = project_uuid
        self.meas_uuid = meas_uuid
        self.reader = reader
        self.caliculator = calculator
        self.writer = writer
        self.fetch_size = fetch_size

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
          - 計測完了
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

        # 計測完了
        self.writer.complete_measurement()
        logging.info(f"Completed measurement: {measurement_dst.uuid}")
