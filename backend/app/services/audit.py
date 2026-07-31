from sqlalchemy.orm import Session

from app.models.operation_log import LogCategory, LogStatus, OperationLog
from app.models.user import User


def add_operation_log(
    db: Session,
    *,
    category: LogCategory,
    action: str,
    status: LogStatus,
    message: str,
    actor: User | None = None,
    employee_id: str | None = None,
    image_id: int | None = None,
    target: str | None = None,
    details: str | None = None,
) -> OperationLog:
    """在当前事务中写入操作日志，由调用方统一提交。"""
    log = OperationLog(
        category=category,
        action=action,
        status=status,
        actor_id=actor.id if actor else None,
        actor_username=actor.username if actor else None,
        employee_id=employee_id or (actor.employee_id if actor else None),
        image_id=image_id,
        target=target,
        message=message[:4000],
        details=details[:8000] if details else None,
    )
    db.add(log)
    return log
