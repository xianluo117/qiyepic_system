from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LogCategory(StrEnum):
    AUTH = "auth"
    USER = "user"
    IMAGE = "image"
    PROCESSING = "processing"


class LogStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    INFO = "info"


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[LogCategory] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[LogStatus] = mapped_column(String(16), index=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    employee_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    image_id: Mapped[int | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )
