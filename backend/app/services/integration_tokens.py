"""为 Agent 集成签发、校验和撤销独立的服务令牌。"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration_token import IntegrationToken
from app.models.user import User

SCOPES = frozenset({"images:read", "images:upload", "images:reprocess"})


def create_token(
    db: Session, user: User, name: str, scopes: set[str], days: int,
) -> tuple[IntegrationToken, str]:
    if (
        not name.strip() or len(name) > 128 or not scopes
        or not scopes <= SCOPES or not 1 <= days <= 365
    ):
        raise ValueError("令牌名称、权限或有效期无效")
    secret = "qimg_" + secrets.token_urlsafe(40)
    now = datetime.now(UTC).replace(tzinfo=None)
    record = IntegrationToken(
        user_id=user.id,
        name=name.strip(),
        token_hash=hashlib.sha256(secret.encode()).hexdigest(),
        scopes=",".join(sorted(scopes)),
        created_at=now,
        expires_at=now + timedelta(days=days),
    )
    db.add(record)
    db.flush()
    return record, secret


def resolve_token(db: Session, secret: str, scope: str) -> tuple[User, IntegrationToken] | None:
    if not secret.startswith("qimg_") or len(secret) > 256:
        return None
    digest = hashlib.sha256(secret.encode()).hexdigest()
    record = db.scalar(select(IntegrationToken).where(IntegrationToken.token_hash == digest))
    if record is None or record.revoked_at is not None:
        return None
    if record.expires_at <= datetime.now(UTC).replace(tzinfo=None):
        return None
    if scope not in record.scopes.split(",") or not record.user.is_active:
        return None
    return record.user, record
