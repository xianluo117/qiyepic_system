"""COS 故障兜底：完整本地文件 + 数据库待办，按对象串行协调。"""
import mimetypes
import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from qcloud_cos.cos_exception import CosClientError, CosServiceError
from requests.exceptions import RequestException
from sqlalchemy import or_, select

from app.core.database import SessionLocal
from app.models.image import Image
from app.models.image_version import ImageVersion
from app.models.storage_pending import StoragePending
from app.storage.base import Storage
from app.storage.object_lock import key_hash, object_lock

COS_ERRORS = (CosClientError, CosServiceError, RequestException)


class StorageUnavailable(Exception):
    def __init__(self):
        super().__init__("云存储暂时不可用，且没有可用的本地副本，请稍后重试")


def referenced(db, key: str) -> bool:
    return (
        db.scalar(select(Image.id).where(or_(
            Image.original_path == key, Image.processed_path == key,
        )).limit(1)) is not None
        or db.scalar(select(ImageVersion.id).where(
            ImageVersion.processed_path == key,
        ).limit(1)) is not None
    )


class FallbackStorage(Storage):
    def __init__(self, remote: Storage, root: Path, sessions=SessionLocal):
        self.remote = remote
        self.root = root / ".cos-fallback"
        self.root.mkdir(parents=True, exist_ok=True)
        self.sessions = sessions

    def lock(self, key: str):
        return object_lock(self.root, key)

    def _path(self, pending: StoragePending) -> Path:
        return self.root / "objects" / pending.key_hash / pending.revision

    def _pending(self, db, key: str):
        return db.get(StoragePending, key_hash(key))

    def queue_delete(self, db, key: str) -> None:
        """与业务删除在同一事务提交；调用方须持有对象锁。"""
        pending = self._pending(db, key)
        if pending is None:
            pending = StoragePending(
                key_hash=key_hash(key), object_key=key, revision=uuid4().hex,
                content_type="",
            )
            db.add(pending)
        pending.operation = "delete"

    def exists_for_upload(self, key: str) -> bool:
        with self.lock(key), self.sessions() as db:
            pending = self._pending(db, key)
            if pending is not None and not referenced(db, key):
                return False
        try:
            return self.exists(key)
        except StorageUnavailable:
            # 只放宽上传前的探测；真正写入仍优先 COS。
            return False

    def save(self, key: str, source: BinaryIO) -> None:
        self._save(key, source, mimetypes.guess_type(key)[0] or "application/octet-stream")

    def _save(self, key: str, source: BinaryIO, content_type: str) -> None:
        with self.lock(key), self.sessions() as db:
            if referenced(db, key):
                raise FileExistsError(f"文件已经存在: {key}")
            previous = self._pending(db, key)
            previous_path = self._path(previous) if previous is not None else None
            position = source.tell()
            try:
                self.remote.save(key, source)
            except COS_ERRORS:
                source.seek(position)
                revision = uuid4().hex
                pending = StoragePending(
                    key_hash=key_hash(key), object_key=key, operation="upload",
                    revision=revision, content_type=content_type,
                )
                target = self._path(pending)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".uploading")
                try:
                    with temporary.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    temporary.replace(target)
                    db.merge(pending)
                    db.commit()
                finally:
                    temporary.unlink(missing_ok=True)
            else:
                if previous is not None:
                    db.delete(previous)
                    db.commit()
            if previous_path is not None:
                previous_path.unlink(missing_ok=True)

    def upload_from_path(self, key: str, source: Path, content_type: str = "") -> None:
        with source.open("rb") as stream:
            self._save(key, stream, content_type)

    def open(self, key: str, mode: str = "rb") -> BinaryIO:
        if mode != "rb":
            raise ValueError("COS 仅支持以 rb 模式读取")
        with self.lock(key), self.sessions() as db:
            pending = self._pending(db, key)
            if pending is not None and pending.operation != "cleanup":
                if pending.operation == "delete":
                    raise FileNotFoundError(key)
                # 响应持有独立临时流，Windows/Linux 清理都不会中断正在读取的响应。
                stream = tempfile.TemporaryFile()
                try:
                    with self._path(pending).open("rb") as source:
                        shutil.copyfileobj(source, stream)
                    stream.seek(0)
                    return stream
                except BaseException:
                    stream.close()
                    raise
            try:
                return self.remote.open(key)
            except COS_ERRORS as exc:
                if isinstance(exc, CosServiceError) and exc.get_status_code() == 404:
                    raise FileNotFoundError(key) from exc
                raise StorageUnavailable() from exc

    def exists(self, key: str) -> bool:
        with self.lock(key), self.sessions() as db:
            pending = self._pending(db, key)
            if pending is not None and pending.operation != "cleanup":
                return pending.operation == "upload" and self._path(pending).is_file()
            try:
                return self.remote.exists(key)
            except COS_ERRORS as exc:
                raise StorageUnavailable() from exc

    def get_size(self, key: str) -> int:
        with self.lock(key), self.sessions() as db:
            pending = self._pending(db, key)
            if pending is not None and pending.operation != "cleanup":
                if pending.operation == "delete":
                    raise FileNotFoundError(key)
                return self._path(pending).stat().st_size
            try:
                return self.remote.get_size(key)
            except COS_ERRORS as exc:
                raise StorageUnavailable() from exc

    def get_download_url(
        self,
        key: str,
        media_type: str,
        filename: str,
        cache_control: str,
        inline: bool = False,
    ) -> str | None:
        with self.lock(key), self.sessions() as db:
            pending = self._pending(db, key)
            if pending is not None and pending.operation != "cleanup":
                return None
            try:
                return self.remote.get_download_url(
                    key, media_type, filename, cache_control, inline,
                )
            except COS_ERRORS as exc:
                raise StorageUnavailable() from exc

    def download_to_path(self, key: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.open(key) as source, target.open("wb") as output:
            try:
                shutil.copyfileobj(source, output)
            except COS_ERRORS as exc:
                raise StorageUnavailable() from exc
        return target

    def delete(self, key: str) -> None:
        with self.lock(key), self.sessions() as db:
            # 异常清理不能删除已经提交的原图或版本。
            if referenced(db, key):
                return
            self.queue_delete(db, key)
            db.commit()
            pending = self._pending(db, key)
            self._path(pending).unlink(missing_ok=True)
            # 删除远端由独立进程执行，不让故障请求阻塞业务。

    def sync_one(self, key: str, revision: str) -> None:
        with self.lock(key), self.sessions() as db:
            pending = self._pending(db, key)
            if pending is None or pending.revision != revision:
                return
            path = self._path(pending)
            if pending.operation == "upload":
                if not referenced(db, key):
                    return
                self.remote.upload_from_path(key, path, pending.content_type)
                # 请求返回成功后再次确认对象可见；任何异常都保留本地副本和待办。
                if not self.remote.exists(key):
                    raise StorageUnavailable()
                pending.operation = "cleanup"
                db.commit()
            elif pending.operation == "delete":
                if referenced(db, key):
                    return
                self.remote.delete(key)
            path.unlink(missing_ok=True)
            db.delete(pending)
            db.commit()
