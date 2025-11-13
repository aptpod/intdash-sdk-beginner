import abc
from pathlib import Path
from typing import Generic, Optional, TypeVar

# ハンドル型（例：BinaryIO, wave.Wave_write など）
H = TypeVar("H")


class BaseWriter(Generic[H], metaclass=abc.ABCMeta):
    """
    ファイル出力抽象基底クラス

    役割:
        - サブクラスでリソース(ファイル/デバイス等)を扱うopen()/close() と with 構文を共通提供
        - 実体のオープン/クローズは open_impl()/close_impl() をサブクラスで実装

    Attributes:
        path (Path): 出力先パス
        _handle (Optional[H]): オープン済みハンドル（内部用）
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        self._handle: Optional[H] = None

    def open(self, mkdirs: bool = True) -> None:
        """
        ファイルオープン

        Args:
            mkdirs: 親ディレクトリ作成
        """
        if self._handle is not None:
            return
        if mkdirs:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.open_impl()

    def close(self) -> None:
        """
        ファイルクローズ

        """
        if self._handle is None:
            return
        try:
            self.close_impl(self._handle)
        finally:
            self._handle = None

    @property
    def handle(self) -> H:
        """
        具体ハンドル

        現在オープン中の具体ハンドルを返す。

        Returns:
            H: サブクラスが返す具体ハンドル

        Raises:
            RuntimeError: 未オープン時
        """
        if self._handle is None:
            raise RuntimeError("Writer is not opened.")
        return self._handle

    # ---- abstract ----------------------------------------------------
    @abc.abstractmethod
    def open_impl(self) -> H:
        """
        オープン

        具体的ハンドルを開いて返す。

        Returns:
            H: オープン済みハンドル
        """
        raise NotImplementedError

    @abc.abstractmethod
    def close_impl(self, h: H) -> None:
        """
        クローズ

        具体的ハンドルを閉じる。

        Args:
            h: close 対象のハンドル
        """
        raise NotImplementedError
