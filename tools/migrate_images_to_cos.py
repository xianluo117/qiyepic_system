"""将本地图片对象迁移到腾讯云 COS。"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.image import Image  # noqa: E402
from app.models.image_version import ImageVersion  # noqa: E402
from app.storage.cos import CosStorage  # noqa: E402
from app.storage.local import LocalStorage  # noqa: E402


def main() -> None:
    source = LocalStorage(settings.image_root)
    target = CosStorage(
        secret_id=settings.cos_secret_id,
        secret_key=settings.cos_secret_key,
        region=settings.cos_region,
        bucket=settings.cos_bucket,
    )
    keys: set[str] = set()
    with SessionLocal() as db:
        for image in db.scalars(select(Image)).all():
            keys.add(image.original_path)
            if image.processed_path:
                keys.add(image.processed_path)
            keys.update(
                version.processed_path
                for version in db.scalars(
                    select(ImageVersion).where(ImageVersion.image_id == image.id),
                ).all()
            )

    uploaded = 0
    total_bytes = 0
    missing_keys: list[str] = []
    for key in sorted(keys):
        local_path = source.get_local_path(key)
        if not local_path.is_file():
            missing_keys.append(key)
            continue
        target.upload_from_path(key, local_path)
        uploaded += 1
        total_bytes += local_path.stat().st_size
        print(f"uploaded {key}")

    print(f"迁移结束：成功上传 {uploaded} 个对象，{total_bytes} 字节；缺失跳过 {len(missing_keys)} 个对象")
    if missing_keys:
        print("缺失文件清单（相对于本地图片根目录）：")
        for key in missing_keys:
            print(f"missing {key}")


if __name__ == "__main__":
    main()
