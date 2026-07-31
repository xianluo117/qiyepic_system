from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models.operation_log import LogCategory, LogStatus, OperationLog
from app.models.user import User
from app.schemas.operation_log import OperationLogResponse

router = APIRouter()


@router.get("", response_model=list[OperationLogResponse])
def list_operation_logs(
    category: LogCategory | None = None,
    log_status: LogStatus | None = Query(default=None, alias="status"),
    employee_id: str | None = None,
    keyword: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[OperationLog]:
    query = select(OperationLog).order_by(OperationLog.created_at.desc()).limit(limit)
    if category:
        query = query.where(OperationLog.category == category)
    if log_status:
        query = query.where(OperationLog.status == log_status)
    if employee_id:
        query = query.where(OperationLog.employee_id == employee_id.strip())
    if keyword:
        value = keyword.strip()
        if value:
            query = query.where(
                OperationLog.message.contains(value)
                | OperationLog.target.contains(value)
                | OperationLog.actor_username.contains(value),
            )
    return list(db.scalars(query).all())
