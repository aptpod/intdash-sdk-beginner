from math import atan2, cos, radians, sin, sqrt


class DistanceCalculator:
    """
    距離算出

    Attributes:
        origin (tuple(float, float)): 原点の緯度経度
    """

    def __init__(self, origin: tuple) -> None:
        self.origin = origin

    def calculate(self, coord: tuple) -> float:
        """
        2点間距離

        Args:
            coord (tuple(float, float)): (緯度, 経度)

        Returns:
            float: 距離 (km)
        """
        R = 6371  # 地球の半径
        lat1, lon1 = self.origin
        lat2, lon2 = coord
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        )
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))
