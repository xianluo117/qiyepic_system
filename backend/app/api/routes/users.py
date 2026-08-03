from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_user_manager
from app.core.database import get_db
from app.core.security import hash_password
from app.models.operation_log import LogCategory, LogStatus
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.audit import add_operation_log

router = APIRouter()


def _get_supervisor(supervisor_id: int | None, db: Session) -> User | None:
    if supervisor_id is None:
        return None
    supervisor = db.get(User, supervisor_id)
    if supervisor is None or supervisor.role != UserRole.SUPERVISOR:
        raise HTTPException(status_code=400, detail="指定的主管不存在或角色不正确")
    return supervisor


def _get_manageable_user(user_id: int, manager: User, db: Session) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="员工不存在")
    if manager.role == UserRole.SUPERVISOR and (
        user.role != UserRole.EMPLOYEE or user.supervisor_id != manager.id
    ):
        raise HTTPException(status_code=403, detail="无权管理该员工")
    return user


@router.get("", response_model=list[UserResponse])
def list_users(
    current_manager: User = Depends(require_user_manager),
    db: Session = Depends(get_db),
) -> list[User]:
    query = select(User)
    if current_manager.role == UserRole.SUPERVISOR:
        query = query.where(
            User.role == UserRole.EMPLOYEE,
            User.supervisor_id == current_manager.id,
        )
    return list(db.scalars(query.order_by(User.created_at.desc())).all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_manager: User = Depends(require_user_manager),
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

    if current_manager.role == UserRole.SUPERVISOR:
        if payload.role != UserRole.EMPLOYEE:
            raise HTTPException(status_code=403, detail="主管只能创建员工账号")
        supervisor_id = current_manager.id
    elif payload.role == UserRole.EMPLOYEE:
        supervisor_id = (
            _get_supervisor(payload.supervisor_id, db).id
            if payload.supervisor_id
            else None
        )
    else:
        if payload.supervisor_id is not None:
            raise HTTPException(status_code=400, detail="管理员和主管不能归属其他主管")
        supervisor_id = None

    user = User(
        employee_id=payload.employee_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        supervisor_id=supervisor_id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    add_operation_log(
        db,
        category=LogCategory.USER,
        action="create_user",
        status=LogStatus.SUCCESS,
        actor=current_manager,
        employee_id=user.employee_id,
        target=user.username,
        message=f"创建账号 {user.username}（{user.employee_id}）",
        details=f"role={user.role.value}, supervisor_id={user.supervisor_id}",
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_manager: User = Depends(require_user_manager),
    db: Session = Depends(get_db),
) -> User:
    user = _get_manageable_user(user_id, current_manager, db)
    if user.id == current_manager.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")

    changes: list[str] = []
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes.append("启用账号" if payload.is_active else "禁用账号")
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        changes.append("重置密码")
    if "supervisor_id" in payload.model_fields_set:
        if current_manager.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="仅管理员可以调整员工归属")
        if user.role != UserRole.EMPLOYEE:
            raise HTTPException(status_code=400, detail="只能为员工指定主管")
        supervisor = _get_supervisor(payload.supervisor_id, db)
        user.supervisor_id = supervisor.id if supervisor else None
        changes.append("调整主管归属")

    add_operation_log(
        db,
        category=LogCategory.USER,
        action="update_user",
        status=LogStatus.SUCCESS,
        actor=current_manager,
        employee_id=user.employee_id,
        target=user.username,
        message=f"更新账号 {user.username}：{'、'.join(changes) or '未变更'}",
    )
    db.commit()
    db.refresh(user)
    return user
