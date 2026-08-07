from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ImageStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "sku",
            "normalized_filename",
            name="uq_images_employee_sku_filename",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    employee_id: Mapped[str] = mapped_column(String(64), index=True)
    sku: Mapped[str] = mapped_column(String(128), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    normalized_filename: Mapped[str] = mapped_column(String(255))
    original_path: Mapped[str] = mapped_column(String(1024))
    processed_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    current_version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_ratio_width: Mapped[int] = mapped_column(Integer)
    target_ratio_height: Mapped[int] = mapped_column(Integer)
    min_short_side_px: Mapped[int] = mapped_column(Integer)
    original_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger)
    content_type: Mapped[str] = mapped_column(String(128))
    status: Mapped[ImageStatus] = mapped_column(
        Enum(ImageStatus, native_enum=False, length=16),
        default=ImageStatus.PENDING,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner = relationship("User", back_populates="images")
    versions = relationship(
        "ImageVersion",
        back_populates="image",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ImageVersion.version_number.desc()",
    )
