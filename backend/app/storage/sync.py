"""独立 COS 待办扫描进程，不使用 Celery 执行槽。"""
import logging
import time

from sqlalchemy import select

from app.core.config import settings
from app.models.storage_pending import StoragePending
from app.storage.factory import create_storage
from app.storage.fallback import FallbackStorage

logger = logging.getLogger(__name__)


def scan(storage: FallbackStorage, after: str = "", batch_size: int = 50) -> str:
    with storage.sessions() as db:
        rows = db.execute(select(
            StoragePending.key_hash, StoragePending.object_key, StoragePending.revision,
        ).where(StoragePending.key_hash > after).order_by(
            StoragePending.key_hash,
        ).limit(batch_size)).all()
    for _, key, revision in rows:
        try:
            storage.sync_one(key, revision)
        except Exception:
            logger.exception("COS 对象同步失败，将在后续扫描继续：%s", key)
    return rows[-1][0] if len(rows) == batch_size else ""


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if settings.storage_backend != "cos":
        # 兼容 compose restart 策略；本地模式不创建 COS 客户端、不扫描。
        while True:
            time.sleep(60)
    storage = create_storage()
    after = ""
    while True:
        try:
            after = scan(storage, after)
        except Exception:
            logger.exception("COS 待办扫描失败")
        time.sleep(60)


if __name__ == "__main__":
    main()
