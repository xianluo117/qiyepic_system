from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.user import User, UserRole


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.image_root.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        admin = db.scalar(
            select(User).where(User.username == settings.bootstrap_admin_username),
        )
        if admin is None:
            db.add(
                User(
                    employee_id=settings.bootstrap_admin_employee_id,
                    username=settings.bootstrap_admin_username,
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role=UserRole.ADMIN,
                    is_active=True,
                ),
            )
            try:
                db.commit()
            except IntegrityError:
                # 多个 Uvicorn Worker 首次并行启动时，只有一个负责创建管理员。
                db.rollback()

    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
