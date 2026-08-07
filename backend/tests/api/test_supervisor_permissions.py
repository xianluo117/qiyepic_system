import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-password-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMPLOYEE_ID", "ADMIN")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("IMAGE_ROOT", str(Path(__file__).parent / ".supervisor-image-data"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.api.routes import images as image_routes
from app.core.database import Base, get_db
from app.main import app
from app.models.image import Image, ImageStatus
from app.models.user import User, UserRole

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
current_username = "supervisor"


def override_get_db():
    with Session(engine) as session:
        yield session


def override_current_user():
    with Session(engine) as session:
        return session.query(User).filter(User.username == current_username).one()


def create_image(session: Session, owner: User, image_id: int) -> Image:
    original_path = f"{owner.employee_id}/original/{image_id}.jpg"
    local_path = image_routes._storage.get_local_path(original_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(f"image-{image_id}".encode())
    image = Image(
        owner_id=owner.id,
        employee_id=owner.employee_id,
        sku=f"SKU-{image_id}",
        original_filename=f"image-{image_id}.jpg",
        normalized_filename=f"image-{image_id}.jpg",
        original_path=original_path,
        target_ratio_width=3,
        target_ratio_height=4,
        min_short_side_px=1000,
        original_width=1500,
        original_height=2000,
        file_size=100,
        content_type="image/jpeg",
        status=ImageStatus.FAILED,
    )
    session.add(image)
    return image


def setup_function() -> None:
    global current_username
    current_username = "supervisor"
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        supervisor = User(
            employee_id="S001",
            username="supervisor",
            password_hash="unused",
            role=UserRole.SUPERVISOR,
            is_active=True,
        )
        other_supervisor = User(
            employee_id="S002",
            username="other-supervisor",
            password_hash="unused",
            role=UserRole.SUPERVISOR,
            is_active=True,
        )
        session.add_all([supervisor, other_supervisor])
        session.flush()
        member = User(
            employee_id="E001",
            username="member",
            password_hash="unused",
            role=UserRole.EMPLOYEE,
            supervisor_id=supervisor.id,
            is_active=True,
        )
        outsider = User(
            employee_id="E002",
            username="outsider",
            password_hash="unused",
            role=UserRole.EMPLOYEE,
            supervisor_id=other_supervisor.id,
            is_active=True,
        )
        session.add_all([member, outsider])
        session.flush()
        create_image(session, supervisor, 1)
        create_image(session, member, 2)
        create_image(session, outsider, 3)
        session.commit()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user


def teardown_function() -> None:
    app.dependency_overrides.clear()
    import shutil

    shutil.rmtree(Path(__file__).parent / ".supervisor-image-data", ignore_errors=True)


def test_supervisor_lists_only_self_and_team_images() -> None:
    with TestClient(app) as client:
        response = client.get("/api/images")

    assert response.status_code == 200
    employee_ids = {item["employee_id"] for item in response.json()["items"]}
    assert employee_ids == {"S001", "E001"}


def test_supervisor_can_read_and_download_team_image_but_cannot_modify_it() -> None:
    with TestClient(app) as client:
        detail = client.get("/api/images/2")
        download = client.get("/api/images/2/file/original")
        retry = client.post(
            "/api/images/2/retry",
            json={
                "ratio_width": 1,
                "ratio_height": 1,
                "min_short_side_px": 1500,
            },
        )
        delete = client.delete("/api/images/2")

    assert detail.status_code == 200
    assert download.status_code == 200
    assert download.content == b"image-2"
    assert retry.status_code == 403
    assert delete.status_code == 403


def test_supervisor_can_reprocess_own_successful_image() -> None:
    processed_key = "S001/processed/SKU-1/image-1.png"
    processed_path = image_routes._storage.get_local_path(processed_key)
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_bytes(b"old-processed-image")
    new_processed_path = image_routes._storage.get_local_path(
        "S001/processed/SKU-1/image-1.jpg"
    )
    new_processed_path.write_bytes(b"incomplete-new-image")
    new_processed_path.with_name(".image-1.jpg.processing").write_bytes(
        b"temporary-image"
    )

    with Session(engine) as session:
        image = session.get(Image, 1)
        assert image is not None
        image.status = ImageStatus.SUCCESS
        image.processed_path = processed_key
        image.processed_width = 1500
        image.processed_height = 2000
        session.commit()

    with (
        patch.object(image_routes.process_image, "delay") as delay,
        TestClient(app) as client,
    ):
        response = client.post(
            "/api/images/1/retry",
            json={
                "ratio_width": 4,
                "ratio_height": 5,
                "min_short_side_px": 1600,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["processed_width"] == 1500
    assert response.json()["processed_height"] == 2000
    assert response.json()["target_ratio_width"] == 4
    assert response.json()["target_ratio_height"] == 5
    assert response.json()["min_short_side_px"] == 1600
    assert processed_path.exists()
    assert not new_processed_path.exists()
    assert not new_processed_path.with_name(".image-1.jpg.processing").exists()
    delay.assert_called_once_with(1)


def test_processed_download_uses_jpeg_filename_and_disables_cache() -> None:
    processed_key = "S001/processed/SKU-1/image-1.jpg"
    processed_path = image_routes._storage.get_local_path(processed_key)
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_bytes(b"jpeg-processed-image")

    with Session(engine) as session:
        image = session.get(Image, 1)
        assert image is not None
        image.original_filename = "image-1.png"
        image.normalized_filename = "image-1.png"
        image.content_type = "image/png"
        image.status = ImageStatus.SUCCESS
        image.processed_path = processed_key
        session.commit()

    with TestClient(app) as client:
        response = client.get("/api/images/1/file/processed?v=current-version")

    assert response.status_code == 200
    assert response.content == b"jpeg-processed-image"
    assert response.headers["content-type"] == "image/jpeg"
    assert 'filename="image-1.jpg"' in response.headers["content-disposition"]
    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )


def test_supervisor_cannot_read_other_team_image() -> None:
    with TestClient(app) as client:
        response = client.get("/api/images/3")

    assert response.status_code == 403


def test_supervisor_can_create_and_manage_only_direct_employee() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/users",
            json={
                "employee_id": "E003",
                "username": "new-member",
                "password": "password-123",
                "role": "employee",
            },
        )
        forbidden_role = client.post(
            "/api/users",
            json={
                "employee_id": "S003",
                "username": "new-supervisor",
                "password": "password-123",
                "role": "supervisor",
            },
        )
        outsider_update = client.patch("/api/users/4", json={"is_active": False})

    assert created.status_code == 201
    assert created.json()["supervisor_id"] == 1
    assert forbidden_role.status_code == 403
    assert outsider_update.status_code == 403
