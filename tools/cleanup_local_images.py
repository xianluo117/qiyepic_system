"""校验 COS 内容后清理数据库引用的本地图片副本，默认仅预览。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def digest_stream(stream) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def fingerprint(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def candidate_path(root: Path, key: str) -> Path | None:
    relative = PurePosixPath(key)
    parts = relative.parts
    if (
        relative.is_absolute() or "\\" in key or ".." in parts
        or len(parts) < 4 or parts[1] not in {"original", "processed"}
        or any(part.startswith(".") for part in parts)
    ):
        return None
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            return None
    if not path.resolve().is_relative_to(root):
        return None
    return path


def check_file(root: Path, key: str, remote, delete: bool, record: dict) -> str:
    path = candidate_path(root, key)
    if path is None:
        return "protected"
    record["local_path"] = str(path)
    if not path.exists():
        return "local_missing"
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        return "protected"
    record["local_size"] = before.st_size
    if not remote.exists(key):
        return "cos_missing"
    record["cos_size"] = remote.get_size(key)
    if before.st_size != record["cos_size"]:
        return "size_mismatch"
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if fingerprint(opened)[:4] != fingerprint(before)[:4]:
            return "local_changed"
        record["local_read_bytes"], record["local_sha256"] = digest_stream(stream)
        if fingerprint(os.fstat(stream.fileno())) != fingerprint(opened):
            return "local_changed"
    with closing(remote.open(key)) as stream:
        record["cos_read_bytes"], record["cos_sha256"] = digest_stream(stream)
    if candidate_path(root, key) != path or fingerprint(path.stat()) != fingerprint(before):
        return "local_changed"
    if not (
        record["local_read_bytes"] == record["cos_read_bytes"] == before.st_size
        and record["local_sha256"] == record["cos_sha256"]
    ):
        return "content_mismatch"
    if delete:
        path.unlink()
        return "deleted"
    return "matched"


def run_cleanup(keys, root: Path, remote, delete: bool, report_path: Path, metadata: dict) -> dict:
    counts: Counter = Counter()
    matched_bytes = deleted_bytes = 0
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as report:
        def write_record(record: dict) -> None:
            report.write(json.dumps(record, ensure_ascii=False) + "\n")
            report.flush()
            os.fsync(report.fileno())

        write_record({"type": "run", "time": datetime.now(timezone.utc).isoformat(),
                      "mode": "delete" if delete else "preview", "root": str(root), **metadata})
        completed = False
        try:
            for key in keys:
                record = {"type": "object", "key": key, **metadata}
                try:
                    result = check_file(root, key, remote, delete, record)
                except Exception as exc:
                    counts["error"] += 1
                    write_record({**record, "status": "error", "error": str(exc)})
                    raise
                counts[result] += 1
                if result in {"matched", "deleted"}:
                    matched_bytes += record["local_size"]
                if result == "deleted":
                    deleted_bytes += record["local_size"]
                write_record({**record, "status": result})
                print(f"{result} {key}", flush=True)
            completed = True
        finally:
            summary = {
                "type": "summary", "completed": completed, "counts": dict(counts),
                "matched_bytes": matched_bytes, "deleted_bytes": deleted_bytes,
                "retained_count": sum(counts.values()) - counts["deleted"],
            }
            write_record(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="重新校验后删除匹配的本地副本")
    parser.add_argument("--report", type=Path, required=True, help="新建 JSONL 报告，须保存到宿主机挂载目录")
    args = parser.parse_args()

    from sqlalchemy import select, union

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.image import Image
    from app.models.image_version import ImageVersion
    from app.storage.cos import CosStorage

    if settings.storage_backend != "cos":
        parser.error("仅允许在 STORAGE_BACKEND=cos 时校验或清理")
    root = settings.image_root.absolute()
    if root.is_symlink() or root.resolve() != root or not root.is_dir():
        parser.error("图片根目录必须是已存在且不经过符号链接的目录")
    remote = CosStorage(settings.cos_secret_id, settings.cos_secret_key,
                        settings.cos_region, settings.cos_bucket)
    query = union(
        select(Image.original_path),
        select(Image.processed_path).where(Image.processed_path.is_not(None)),
        select(ImageVersion.processed_path),
    )
    with SessionLocal() as db:
        keys = sorted(db.scalars(query).all())
    run_cleanup(keys, root, remote, args.delete, args.report,
                {"bucket": settings.cos_bucket, "region": settings.cos_region})


if __name__ == "__main__":
    main()
