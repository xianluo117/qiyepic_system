from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.operation_log import LogCategory, LogStatus
from app.models.user import User
from app.schemas.user import TokenResponse, UserResponse
from app.services.audit import add_operation_log

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == form.username))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        add_operation_log(
            db,
            category=LogCategory.AUTH,
            action="login",
            status=LogStatus.FAILED,
            actor=user,
            target=form.username,
            message=f"账号 {form.username} 登录失败",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    add_operation_log(
        db,
        category=LogCategory.AUTH,
        action="login",
        status=LogStatus.SUCCESS,
        actor=user,
        target=user.username,
        message=f"账号 {user.username} 登录成功",
    )
    db.commit()
    token = create_access_token(user.username, user.role.value)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
