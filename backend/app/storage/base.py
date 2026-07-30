from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class Storage(ABC):
    """图片存储统一接口。"""

    @abstractmethod
    def save(self, key: str, source: BinaryIO) -> Path:
        raise NotImplementedError

    @abstractmethod
    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_size(self, key: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_local_path(self, key: str) -> Path:
        raise NotImplementedError
