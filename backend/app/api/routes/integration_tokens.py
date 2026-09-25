from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.integration_token import IntegrationToken
from app.models.operation_log import LogCategory, LogStatus
from app.models.user import User
from app.schemas.integration_token import TokenCreate, TokenCreated, TokenInfo
from app.services.audit import add_operation_log
from app.services.integration_tokens import SCOPES, create_token

router = APIRouter()


def _info(record: IntegrationToken) -> TokenInfo:
    return TokenInfo(
        id=record.id, name=record.name, scopes=record.scopes.split(","),
        created_at=record.created_at, expires_at=record.expires_at,
        revoked_at=record.revoked_at,
    )


@router.post("", response_model=TokenCreated, status_code=201)
def issue_token(
    payload: TokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenCreated:
    if not payload.scopes <= SCOPES:
        raise HTTPException(status_code=422, detail="包含不支持的集成权限")
    record, secret = create_token(
        db, current_user, payload.name, payload.scopes, payload.expires_in_days,
    )
    add_operation_log(db, category=LogCategory.AUTH, action="create_integration_token",
                      status=LogStatus.SUCCESS, actor=current_user,
                      target=str(record.id), message=f"创建集成令牌 {record.name}")
    db.commit()
    return TokenCreated(**_info(record).model_dump(), token=secret)


@router.get("", response_model=list[TokenInfo])
def list_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TokenInfo]:
    records = db.scalars(select(IntegrationToken).where(IntegrationToken.user_id == current_user.id)
                         .order_by(IntegrationToken.id.desc())).all()
    return [_info(record) for record in records]


@router.delete("/{token_id}", status_code=204)
def revoke_token(
    token_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    record = db.scalar(select(IntegrationToken).where(IntegrationToken.id == token_id,
                                                     IntegrationToken.user_id == current_user.id))
    if record is None:
        raise HTTPException(status_code=404, detail="集成令牌不存在")
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC).replace(tzinfo=None)
        add_operation_log(db, category=LogCategory.AUTH, action="revoke_integration_token",
                          status=LogStatus.SUCCESS, actor=current_user,
                          target=str(record.id), message=f"撤销集成令牌 {record.name}")
        db.commit()
