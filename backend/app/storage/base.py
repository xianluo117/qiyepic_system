import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

_SAFE_SEGMENT = re.compile(r"^[^/\\\x00-\x1f]+$")


class Storage(ABC):
    """图片对象存储统一接口。"""

    @classmethod
    def build_key(cls, employee_id: str, image_type: str, sku: str, filename: str) -> str:
        if image_type not in {"original", "processed"}:
            raise ValueError("图片目录类型必须是 original 或 processed")

        segments = (employee_id, image_type, sku, Path(filename).name)
        for segment in segments:
            Storage.validate_segment(segment)
        return "/".join(segments)

    @abstractmethod
    def save(self, key: str, source: BinaryIO) -> None:
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
    def download_to_path(self, key: str, target: Path) -> Path:
        raise NotImplementedError

    def get_download_url(
        self,
        key: str,
        media_type: str,
        filename: str,
        cache_control: str,
        inline: bool = False,
    ) -> str | None:
        return None

    @abstractmethod
    def upload_from_path(self, key: str, source: Path, content_type: str = "") -> None:
        raise NotImplementedError

    @classmethod
    def validate_segment(cls, segment: str) -> None:
        if not segment or segment in {".", ".."} or not _SAFE_SEGMENT.fullmatch(segment):
            raise ValueError(f"非法路径字段: {segment!r}")
