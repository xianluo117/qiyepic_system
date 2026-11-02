"""图片存储模块。"""

from app.storage.base import Storage
from app.storage.cos import CosStorage
from app.storage.factory import create_storage
from app.storage.local import LocalStorage

__all__ = ["CosStorage", "LocalStorage", "Storage", "create_storage"]
