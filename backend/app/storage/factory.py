from app.core.config import settings
from app.storage.base import Storage
from app.storage.cos import CosStorage
from app.storage.local import LocalStorage


def create_storage() -> Storage:
    if settings.storage_backend == "cos":
        return CosStorage(
            secret_id=settings.cos_secret_id,
            secret_key=settings.cos_secret_key,
            region=settings.cos_region,
            bucket=settings.cos_bucket,
        )
    return LocalStorage(settings.image_root)
