"""集成令牌的摘要、权限、过期及撤销校验。"""

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-long-enough-123456")
os.environ.setdefault("BOOTSTRAP_ADMIN_USERNAME", "admin")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "admin-password-123")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMPLOYEE_ID", "ADMIN")
os.environ.setdefault("DATABASE_URL_OVERRIDE", "sqlite://")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.integration_tokens import create_token, resolve_token  # noqa: E402


def test_token_lifecycle():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            user = User(username="agent", employee_id="agent", password_hash="unused")
            db.add(user)
            db.flush()
            token, secret = create_token(db, user, "project-a", {"images:read"}, 1)
            db.commit()
            assert secret not in token.token_hash
            assert len(token.token_hash) == 64
            assert resolve_token(db, secret, "images:read")[0].id == user.id
            assert resolve_token(db, secret, "images:upload") is None
            user.is_active = False
            assert resolve_token(db, secret, "images:read") is None
            user.is_active = True
            now = datetime.now(UTC).replace(tzinfo=None)
            token.expires_at = now - timedelta(seconds=1)
            assert resolve_token(db, secret, "images:read") is None
            token.expires_at = now + timedelta(days=1)
            token.revoked_at = now
            assert resolve_token(db, secret, "images:read") is None
    finally:
        engine.dispose()
