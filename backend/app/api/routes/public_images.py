from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.image import Image
from app.processing.paths import get_processed_filename
from app.storage.local import LocalStorage

router = APIRouter()
_storage = LocalStorage(settings.image_root)


@router.get("/images/{employee_id}/{sku}/{filename}/{kind}")
def read_public_image(
    employee_id: str,
    sku: str,
    filename: str,
    kind: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    candidates = db.scalars(
        select(Image).where(
            Image.employee_id == employee_id,
            Image.sku == sku,
        )
    ).all()
    matches = [
        image
        for image in candidates
        if Path(image.original_filename).stem == filename
    ]
    if not matches:
        raise HTTPException(status_code=404, detail="公开图片不存在或链接已失效")
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail="存在多个同名但扩展名不同的图片")
    image = matches[0]

    if kind == "original":
        key = image.original_path
        media_type = image.content_type
        filename_for_response = image.original_filename
        cache_control = "public, max-age=31536000, immutable"
    elif kind == "processed":
        key = image.processed_path
        if not key:
            raise HTTPException(status_code=404, detail="处理图尚未生成")
        media_type = "image/jpeg"
        filename_for_response = get_processed_filename(image.original_filename)
        cache_control = "no-store, no-cache, must-revalidate, max-age=0"
    else:
        raise HTTPException(status_code=400, detail="图片类型必须是 original 或 processed")

    path = _storage.get_local_path(key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename_for_response,
        content_disposition_type="inline",
        headers={"Cache-Control": cache_control},
    )
