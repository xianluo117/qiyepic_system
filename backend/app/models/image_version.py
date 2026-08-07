from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ImageVersion(Base):
    __tablename__ = "image_versions"
    __table_args__ = (
        UniqueConstraint(
            "image_id",
            "version_number",
            name="uq_image_versions_image_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"),
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer)
    processed_path: Mapped[str] = mapped_column(String(1024), unique=True)
    ratio_width: Mapped[int] = mapped_column(Integer)
    ratio_height: Mapped[int] = mapped_column(Integer)
    min_short_side_px: Mapped[int] = mapped_column(Integer)
    output_width: Mapped[int] = mapped_column(Integer)
    output_height: Mapped[int] = mapped_column(Integer)
    file_size: Mapped[int] = mapped_column(BigInteger)
    compression_setting: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )

    image = relationship("Image", back_populates="versions")
