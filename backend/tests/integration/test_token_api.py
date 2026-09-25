"""令牌管理与上传 API 的端到端鉴权测试。"""

import io
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-password-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMPLOYEE_ID", "ADMIN")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite://")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.router import api_router  # noqa: E402
from app.api.routes import images  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.user import User  # noqa: E402
from app.storage.local import LocalStorage  # noqa: E402


def test_token_management_and_upload(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(api_router, prefix="/api")

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(images, "_storage", LocalStorage(tmp_path))
    monkeypatch.setattr(images.process_image, "delay", lambda _: None)
    with Session(engine) as db:
        db.add_all([User(username=name, employee_id=name, password_hash="unused")
                    for name in ("owner", "outsider")])
        db.commit()
    login = {"Authorization": "Bearer " + create_access_token("owner", "employee")}
    outsider = {"Authorization": "Bearer " + create_access_token("outsider", "employee")}
    stream = io.BytesIO()
    Image.new("RGB", (20, 20)).save(stream, format="PNG")
    data = {"sku": "SKU", "ratio_width": 1, "ratio_height": 1, "min_short_side_px": 20}
    files = {"files": ("image.png", stream.getvalue(), "image/png")}
    try:
        with TestClient(app) as client:
            created = client.post("/api/integration-tokens", headers=login, json={
                "name": "project-a", "scopes": ["images:read", "images:upload"],
            })
            assert created.status_code == 201, created.text
            token = created.json()
            headers = {"Authorization": "Bearer " + token["token"]}
            listed = client.get("/api/integration-tokens", headers=login)
            assert "token" not in listed.json()[0]
            assert client.delete(f'/api/integration-tokens/{token["id"]}',
                                 headers=outsider).status_code == 404
            assert client.post("/api/integration-tokens", headers=login, json={
                "name": "   ", "scopes": ["images:read"],
            }).status_code == 422
            assert client.post("/api/integration-tokens", headers=headers, json={
                "name": "forbidden", "scopes": ["images:read"],
            }).status_code == 401
            uploaded = client.post("/api/images/upload", headers=headers, data=data, files=files)
            assert uploaded.status_code == 200, uploaded.text
            assert uploaded.json()["results"][0]["success"] is True
            duplicate = client.post("/api/images/upload", headers=headers, data=data, files=files)
            assert duplicate.json()["results"][0]["success"] is False
            readonly = client.post("/api/integration-tokens", headers=login, json={
                "name": "read-only", "scopes": ["images:read"],
            }).json()["token"]
            assert client.post("/api/images/upload", data=data, files=files,
                               headers={"Authorization": "Bearer " + readonly}).status_code == 403
            assert client.delete(f'/api/integration-tokens/{token["id"]}',
                                 headers=login).status_code == 204
            assert client.post("/api/images/upload", headers=headers,
                               data=data, files=files).status_code == 403
    finally:
        engine.dispose()
