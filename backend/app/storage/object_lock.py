"""共享本地目录上的对象锁；进程退出由操作系统释放，锁文件不能删除。"""
import hashlib
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

_held = threading.local()


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@contextmanager
def object_lock(root: Path, key: str):
    directory = root / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / key_hash(key)
    identity = str(path.resolve())
    held = getattr(_held, "keys", None)
    if held is None:
        held = _held.keys = set()
    if identity in held:
        yield
        return
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            # Windows 允许锁定 EOF 之外的字节，无需写入锁文件。
            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX)
        held.add(identity)
        try:
            yield
        finally:
            held.remove(identity)
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
