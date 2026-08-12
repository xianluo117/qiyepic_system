import os
import shutil
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-password-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMPLOYEE_ID", "ADMIN")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("IMAGE_ROOT", str(Path(__file__).parent / ".public-image-data"))

from fastapi.testclient import TestClient
from PIL import Image as PillowImage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes import public_images
from app.core.database import Base, get_db
from app.main import app
from app.models.image import Image, ImageStatus
from app.models.image_version import ImageVersion
from app.models.user import User, UserRole
from app.services.version_revision import version_number_to_revision

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_db():
    with Session(engine) as session:
        yield session


def create_image(session: Session, suffix: str, processed: bool = True) -> Image:
    user = User(
        employee_id=f"E{suffix}",
        username=f"user-{suffix}",
        password_hash="unused",
        role=UserRole.EMPLOYEE,
        is_active=True,
    )
    session.add(user)
    session.flush()

    original_key = f"{user.employee_id}/original/SKU/{suffix}.jpg"
    processed_key = (
        f"{user.employee_id}/processed/SKU/{suffix}.jpg" if processed else None
    )
    original_path = public_images._storage.get_local_path(original_key)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(b"original-image")
    if processed_key:
        processed_path = public_images._storage.get_local_path(processed_key)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.write_bytes(b"processed-image")

    image = Image(
        owner_id=user.id,
        employee_id=user.employee_id,
        sku="SKU",
        original_filename=f"{suffix}.jpg",
        normalized_filename=f"{suffix}.jpg",
        original_path=original_key,
        processed_path=processed_key,
        target_ratio_width=3,
        target_ratio_height=4,
        min_short_side_px=1000,
        original_width=1500,
        original_height=2000,
        processed_width=1500 if processed else None,
        processed_height=2000 if processed else None,
        file_size=14,
        content_type="image/jpeg",
        status=ImageStatus.SUCCESS if processed else ImageStatus.PENDING,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return image


def create_version(
    session: Session,
    image: Image,
    version_number: int = 1,
) -> ImageVersion:
    processed_key = (
        f"{image.employee_id}/processed/{image.sku}/"
        f"{Path(image.original_filename).stem}.image-{image.id}.v{version_number}.jpg"
    )
    processed_path = public_images._storage.get_local_path(processed_key)
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_bytes(f"version-{version_number}".encode())
    version = ImageVersion(
        image_id=image.id,
        version_number=version_number,
        processed_path=processed_key,
        ratio_width=3,
        ratio_height=4,
        min_short_side_px=1000,
        output_width=1500,
        output_height=2000,
        file_size=len(f"version-{version_number}"),
        compression_setting="quality=90",
    )
    session.add(version)
    image.processed_path = processed_key
    image.current_version_number = version_number
    image.status = ImageStatus.SUCCESS
    session.commit()
    session.refresh(version)
    return version


def setup_function() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_db] = override_get_db


def teardown_function() -> None:
    app.dependency_overrides.clear()
    shutil.rmtree(Path(__file__).parent / ".public-image-data", ignore_errors=True)


def test_public_original_and_processed_images_are_accessible_by_descriptive_url() -> None:
    with Session(engine) as session:
        create_image(session, "001")

    with TestClient(app) as client:
        base_url = "/api/public/images/E001/SKU/001"
        original = client.get(f"{base_url}/original")
        processed = client.get(f"{base_url}/processed")

    assert original.status_code == 200
    assert original.content == b"original-image"
    assert original.headers["content-type"] == "image/jpeg"
    assert processed.status_code == 200
    assert processed.content == b"processed-image"
    assert processed.headers["content-type"] == "image/jpeg"
    assert 'filename="001.jpg"' in processed.headers["content-disposition"]
    assert original.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    assert processed.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )


def test_public_image_rejects_unknown_employee_mismatched_path_and_missing_file() -> None:
    with Session(engine) as session:
        create_image(session, "002", processed=False)

    with TestClient(app) as client:
        unknown = client.get("/api/public/images/UNKNOWN/SKU/002/original")
        mismatched = client.get("/api/public/images/E002/WRONG/002/original")
        missing_processed = client.get(
            "/api/public/images/E002/SKU/002/processed"
        )

    assert unknown.status_code == 404
    assert mismatched.status_code == 404
    assert missing_processed.status_code == 404


def test_versioned_public_url_reads_requested_immutable_revision() -> None:
    with Session(engine) as session:
        image = create_image(session, "004", processed=False)
        create_version(session, image)
        image_id = image.id

    revision_one = version_number_to_revision(1)
    revision_two = version_number_to_revision(2)
    with TestClient(app) as client:
        base_url = f"/api/public/images/{image_id}/E004/SKU/004"
        original = client.get(f"{base_url}/original")
        processed = client.get(f"{base_url}/processed?rev={revision_one}")
        missing_version = client.get(f"{base_url}/processed?rev={revision_two}")
        mismatched = client.get(
            f"/api/public/images/{image_id}/WRONG/SKU/004/processed?rev={revision_one}"
        )
        legacy = client.get(f"{base_url}/processed?v=1")

    assert revision_one == "abcd"
    assert original.status_code == 200
    assert processed.status_code == 200
    assert processed.content == b"version-1"
    assert processed.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing_version.status_code == 404
    assert mismatched.status_code == 404
    assert legacy.status_code == 200
    assert legacy.content == b"version-1"


def test_public_url_without_image_id_reads_requested_version() -> None:
    with Session(engine) as session:
        image = create_image(session, "007", processed=False)
        create_version(session, image, version_number=1)
        create_version(session, image, version_number=2)

    revision_two = version_number_to_revision(2)
    with TestClient(app) as client:
        base_url = "/api/public/images/E007/SKU/007"
        original = client.get(f"{base_url}/original")
        version_one = client.get(f"{base_url}/processed?v=1")
        version_two = client.get(f"{base_url}/processed?rev={revision_two}")
        missing_version = client.get(f"{base_url}/processed?v=3")
        missing_parameter = client.get(f"{base_url}/processed")

    assert original.status_code == 200
    assert original.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    assert version_one.status_code == 200
    assert version_one.content == b"version-1"
    assert version_one.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    assert version_two.status_code == 200
    assert version_two.content == b"version-2"
    assert missing_version.status_code == 404
    assert missing_parameter.status_code == 422


def test_public_processed_url_rejects_invalid_or_conflicting_revision_parameters() -> None:
    with Session(engine) as session:
        image = create_image(session, "008", processed=False)
        create_version(session, image)
        image_id = image.id

    with TestClient(app) as client:
        base_url = f"/api/public/images/{image_id}/E008/SKU/008/processed"
        invalid = client.get(f"{base_url}?rev=ab1d")
        uppercase = client.get(f"{base_url}?rev=ABCD")
        conflicting = client.get(f"{base_url}?rev=abcd&v=1")
        missing = client.get(base_url)

    assert invalid.status_code == 422
    assert uppercase.status_code == 422
    assert conflicting.status_code == 400
    assert missing.status_code == 422


def test_public_thumbnail_is_generated_cached_and_invalidated_by_database() -> None:
    with Session(engine) as session:
        image = create_image(session, "006", processed=False)
        source_path = public_images._storage.get_local_path(image.original_path)
        PillowImage.new("RGBA", (900, 450), (0, 0, 255, 0)).save(
            source_path,
            format="PNG",
        )
        image.content_type = "image/png"
        session.commit()
        image_id = image.id

    with TestClient(app) as client:
        first = client.get(f"/api/public/images/{image_id}/thumbnail")
        cached_path = public_images._thumbnails.get_path(image_id)
        first_mtime = cached_path.stat().st_mtime_ns
        second = client.get(f"/api/public/images/{image_id}/thumbnail")

    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"
    assert first.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert second.content == first.content
    assert cached_path.stat().st_mtime_ns == first_mtime

    thumbnail_copy = Path(__file__).parent / ".thumbnail-copy.jpg"
    thumbnail_copy.write_bytes(first.content)
    try:
        with PillowImage.open(thumbnail_copy) as thumbnail:
            assert thumbnail.size == (360, 180)
            red, green, blue = thumbnail.getpixel((180, 90))
            assert red >= 245
            assert green >= 245
            assert blue >= 245
    finally:
        thumbnail_copy.unlink(missing_ok=True)

    with Session(engine) as session:
        stored = session.get(Image, image_id)
        assert stored is not None
        session.delete(stored)
        session.commit()

    with TestClient(app) as client:
        deleted = client.get(f"/api/public/images/{image_id}/thumbnail")

    assert deleted.status_code == 404


def test_public_descriptive_link_stops_working_after_image_is_deleted() -> None:
    with Session(engine) as session:
        image = create_image(session, "003")
        session.delete(image)
        session.commit()

    with TestClient(app) as client:
        response = client.get("/api/public/images/E003/SKU/003/original")

    assert response.status_code == 404


def test_all_versioned_public_links_stop_working_after_image_is_deleted() -> None:
    with Session(engine) as session:
        image = create_image(session, "005", processed=False)
        create_version(session, image)
        image_id = image.id
        session.delete(image)
        session.commit()

    revision = version_number_to_revision(1)
    with TestClient(app) as client:
        versioned = client.get(
            f"/api/public/images/{image_id}/E005/SKU/005/processed?rev={revision}"
        )
        descriptive = client.get(
            f"/api/public/images/E005/SKU/005/processed?rev={revision}"
        )

    assert versioned.status_code == 404
    assert descriptive.status_code == 404
