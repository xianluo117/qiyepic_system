from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StoragePending(Base):
    __tablename__ = "storage_pending"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    object_key: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(String(16))
    revision: Mapped[str] = mapped_column(String(32))
    content_type: Mapped[str] = mapped_column(String(128), default="")
