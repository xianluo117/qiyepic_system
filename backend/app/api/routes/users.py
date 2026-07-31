from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.operation_log import LogCategory, LogStatus
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.audit import add_operation_log

router = APIRouter()


@router.get("", response_model=list[UserResponse])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    duplicate = db.scalar(
        select(User).where(
            or_(
                User.username == payload.username,
                User.employee_id == payload.employee_id,
            ),
        ),
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名或员工 ID 已存在",
        )

    user = User(
        employee_id=payload.employee_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    add_operation_log(
        db,
        category=LogCategory.USER,
        action="create_user",
        status=LogStatus.SUCCESS,
        actor=current_admin,
        employee_id=user.employee_id,
        target=user.username,
        message=f"创建账号 {user.username}（{user.employee_id}）",
        details=f"role={user.role.value}",
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="员工不存在")
    if user.id == current_admin.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="管理员不能禁用自己的账号")

    changes: list[str] = []
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes.append("启用账号" if payload.is_active else "禁用账号")
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        changes.append("重置密码")

    add_operation_log(
        db,
        category=LogCategory.USER,
        action="update_user",
        status=LogStatus.SUCCESS,
        actor=current_admin,
        employee_id=user.employee_id,
        target=user.username,
        message=f"更新账号 {user.username}：{'、'.join(changes) or '未变更'}",
    )
    db.commit()
    db.refresh(user)
    return user
