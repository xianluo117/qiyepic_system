from fastapi import APIRouter

from app.api.routes import auth, images, logs, public_images, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(public_images.router, prefix="/public", tags=["public-images"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(logs.router, prefix="/admin/logs", tags=["admin-logs"])
