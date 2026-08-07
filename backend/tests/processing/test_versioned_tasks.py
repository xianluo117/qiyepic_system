import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-password-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMPLOYEE_ID", "ADMIN")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("IMAGE_ROOT", str(Path(__file__).parent / ".version-task-data"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.image import Image, ImageStatus
from app.models.image_version import ImageVersion
from app.models.user import User, UserRole
from app.processing.processor import ImageProcessResult
from worker.tasks import image_tasks

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def setup_function() -> None:
    image_tasks.Base = None  # type: ignore[attr-defined]
    from app.core.database import Base

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    root = Path(os.environ["IMAGE_ROOT"])
    root.mkdir(parents=True, exist_ok=True)

    with Session(engine) as session:
        user = User(
            employee_id="E001",
            username="employee",
            password_hash="unused",
            role=UserRole.EMPLOYEE,
            is_active=True,
        )
        session.add(user)
        session.flush()
        original_key = "E001/original/SKU/source.png"
        original_path = root / original_key
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(b"original")
        session.add(
            Image(
                id=1,
                owner_id=user.id,
                employee_id="E001",
                sku="SKU",
                original_filename="source.png",
                normalized_filename="source.png",
                original_path=original_key,
                target_ratio_width=3,
                target_ratio_height=4,
                min_short_side_px=1500,
                original_width=100,
                original_height=100,
                file_size=8,
                content_type="image/png",
                status=ImageStatus.PENDING,
            )
        )
        session.commit()


def teardown_function() -> None:
    import shutil

    shutil.rmtree(Path(os.environ["IMAGE_ROOT"]), ignore_errors=True)


def successful_result() -> ImageProcessResult:
    return ImageProcessResult(
        original_width=100,
        original_height=100,
        cropped_width=75,
        cropped_height=100,
        output_width=1500,
        output_height=2000,
        output_file_size=1000,
        compression_setting="quality=90",
        enlarged=True,
        reduced_for_size_limit=False,
    )


def fake_process(*, target_path: Path, **_: object) -> ImageProcessResult:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(b"processed")
    return successful_result()


def test_processing_creates_independent_versions_and_keeps_latest_ten() -> None:
    with (
        patch.object(image_tasks, "SessionLocal", lambda: Session(engine)),
        patch.object(image_tasks.ImageProcessor, "process", side_effect=fake_process),
    ):
        for _ in range(11):
            image_tasks.process_image.run(1)

    with Session(engine) as session:
        image = session.get(Image, 1)
        assert image is not None
        versions = list(
            session.scalars(
                select(ImageVersion)
                .where(ImageVersion.image_id == 1)
                .order_by(ImageVersion.version_number)
            ).all()
        )

    assert [version.version_number for version in versions] == list(range(2, 12))
    assert image.current_version_number == 11
    assert image.processed_path is not None
    assert image.processed_path.endswith("source.image-1.v11.jpg")
    expired_path = (
        Path(os.environ["IMAGE_ROOT"])
        / "E001/processed/SKU/source.image-1.v1.jpg"
    )
    assert not expired_path.exists()
    assert (Path(os.environ["IMAGE_ROOT"]) / image.processed_path).exists()


def test_failed_reprocess_preserves_current_successful_version() -> None:
    with (
        patch.object(image_tasks, "SessionLocal", lambda: Session(engine)),
        patch.object(image_tasks.ImageProcessor, "process", side_effect=fake_process),
    ):
        image_tasks.process_image.run(1)

    with (
        patch.object(image_tasks, "SessionLocal", lambda: Session(engine)),
        patch.object(
            image_tasks.ImageProcessor,
            "process",
            side_effect=ValueError("processing failed"),
        ),
    ):
        try:
            image_tasks.process_image.run(1)
        except ValueError:
            pass
        else:
            raise AssertionError("处理失败时任务应抛出异常")

    with Session(engine) as session:
        image = session.get(Image, 1)
        assert image is not None
        versions = list(session.scalars(select(ImageVersion)).all())

    assert image.status == ImageStatus.SUCCESS
    assert image.current_version_number == 1
    assert image.processed_path is not None
    assert image.processed_path.endswith("source.image-1.v1.jpg")
    assert image.error_message == "processing failed"
    assert len(versions) == 1
    assert (Path(os.environ["IMAGE_ROOT"]) / image.processed_path).exists()
