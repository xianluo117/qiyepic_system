import re
import shutil
from pathlib import Path
from typing import BinaryIO

from app.storage.base import Storage

_SAFE_SEGMENT = re.compile(r"^[^/\\\x00-\x1f]+$")


class LocalStorage(Storage):
    """基于 Linux 本地目录的图片存储实现。"""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def build_key(
        self,
        employee_id: str,
        image_type: str,
        sku: str,
        filename: str,
    ) -> str:
        if image_type not in {"original", "processed"}:
            raise ValueError("图片目录类型必须是 original 或 processed")

        segments = (employee_id, image_type, sku, Path(filename).name)
        for segment in segments:
            self._validate_segment(segment)

        return "/".join(segments)

    def save(self, key: str, source: BinaryIO) -> Path:
        target = self.get_local_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            raise FileExistsError(f"文件已经存在: {key}")

        temporary = target.with_name(f".{target.name}.uploading")
        try:
            with temporary.open("xb") as output:
                shutil.copyfileobj(source, output)
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        return target

    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        return self.get_local_path(key).open(mode)

    def exists(self, key: str) -> bool:
        return self.get_local_path(key).is_file()

    def delete(self, key: str) -> None:
        self.get_local_path(key).unlink(missing_ok=True)

    def get_size(self, key: str) -> int:
        return self.get_local_path(key).stat().st_size

    def get_local_path(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute():
            raise ValueError("存储键不能是绝对路径")

        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("存储键超出图片根目录")
        return target

    @staticmethod
    def _validate_segment(segment: str) -> None:
        if not segment or segment in {".", ".."} or not _SAFE_SEGMENT.fullmatch(segment):
            raise ValueError(f"非法路径字段: {segment!r}")
