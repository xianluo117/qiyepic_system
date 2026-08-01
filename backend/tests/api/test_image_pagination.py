import os
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-password-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMPLOYEE_ID", "ADMIN")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("IMAGE_ROOT", str(Path(__file__).parent / ".pagination-image-data"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.models.image import Image, ImageStatus
from app.models.user import User, UserRole

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_db():
    with Session(engine) as session:
        yield session


def setup_function() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

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
        for index in range(55):
            session.add(
                Image(
                    owner_id=user.id,
                    employee_id=user.employee_id,
                    sku=f"SKU-{index:03d}",
                    original_filename=f"image-{index:03d}.jpg",
                    normalized_filename=f"image-{index:03d}.jpg",
                    public_token=f"{index:032x}",
                    original_path=f"original/{index}.jpg",
                    target_ratio_width=3,
                    target_ratio_height=4,
                    min_short_side_px=1000,
                    original_width=1500,
                    original_height=2000,
                    file_size=100,
                    content_type="image/jpeg",
                    status=ImageStatus.SUCCESS,
                ),
            )
        session.commit()

    app.dependency_overrides[get_db] = override_get_db

    def override_current_user():
        with Session(engine) as session:
            return session.query(User).filter(User.username == "employee").one()

    app.dependency_overrides[get_current_user] = override_current_user


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_image_list_uses_default_page_size_50() -> None:
    with TestClient(app) as client:
        response = client.get("/api/images")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 55
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert len(payload["items"]) == 50


def test_image_list_can_read_next_page_and_change_page_size() -> None:
    with TestClient(app) as client:
        second_page = client.get("/api/images?page=2&page_size=50")
        custom_size = client.get("/api/images?page=3&page_size=20")

    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 5
    assert custom_size.status_code == 200
    assert custom_size.json()["page"] == 3
    assert len(custom_size.json()["items"]) == 15
