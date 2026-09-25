"""远程 MCP 协议及撤销验证；独立应用避免改变原有应用的生命周期。"""

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-password-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMPLOYEE_ID", "ADMIN")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite://")
os.environ.setdefault("IMAGE_ROOT", str(Path.cwd()))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.mcp import auth, server  # noqa: E402
from app.models.integration_token import IntegrationToken  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.integration_tokens import create_token  # noqa: E402


def test_mcp_identity_is_request_scoped(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(auth, "SessionLocal", sessions)
    monkeypatch.setattr(server, "SessionLocal", sessions)
    monkeypatch.setattr(settings, "public_base_url", "http://testserver")
    security = server.mcp.settings.transport_security
    monkeypatch.setattr(security, "allowed_hosts", ["testserver"])
    monkeypatch.setattr(security, "allowed_origins", ["http://testserver"])
    # 每次测试重新创建 session manager，它不支持停止后再次启动。
    monkeypatch.setattr(server.mcp, "_session_manager", None)
    transport = server.mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_):
        async with server.mcp.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.mount("/mcp", auth.IntegrationAuthMiddleware(transport))
    with sessions() as db:
        user = User(employee_id="agent-1", username="agent-1", password_hash="x")
        db.add(user)
        db.commit()
        record, secret = create_token(db, user, "read only", {"images:read"}, 1)
        token_id = record.id
        db.commit()
    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    }}
    try:
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {secret}", "Accept": "application/json"}
            response = client.post("/mcp/", headers=headers, json=payload)
            assert response.status_code == 200, response.text
            assert response.json()["result"]["serverInfo"]["name"] == "图床集成"
            assert client.post("/mcp/", json=payload).status_code == 401
            bad_origin = {**headers, "Origin": "https://other.invalid"}
            assert client.post("/mcp/", headers=bad_origin, json=payload).status_code == 403
            for name, arguments, expected in [
                ("get_image", {"image_id": 999}, 404),
                ("reprocess_image", {"image_id": 999, "ratio_width": 3,
                                     "ratio_height": 4, "min_short_side_px": 100}, 403),
            ]:
                result = client.post("/mcp/", headers=headers, json={
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                })
                assert result.status_code == 200, result.text
                assert result.json()["result"]["isError"] is True
                assert result.json()["result"]["structuredContent"]["error"]["status"] == expected
            with sessions() as db:
                record = db.get(IntegrationToken, token_id)
                record.revoked_at = datetime.now(UTC).replace(tzinfo=None)
                db.commit()
            assert client.post("/mcp/", headers=headers, json=payload).status_code == 401
    finally:
        engine.dispose()
