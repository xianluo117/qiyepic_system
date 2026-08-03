from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.image import Image
from app.storage.local import LocalStorage

router = APIRouter()
_storage = LocalStorage(settings.image_root)


@router.get("/images/{image_id}/{sku}/{filename}/{kind}")
def read_public_image(
    image_id: int,
    sku: str,
    filename: str,
    kind: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="公开图片不存在或链接已失效")

    expected_filename = Path(image.original_filename).stem
    if sku != image.sku or filename != expected_filename:
        raise HTTPException(status_code=404, detail="公开图片地址不匹配")

    if kind == "original":
        key = image.original_path
    elif kind == "processed":
        key = image.processed_path
        if not key:
            raise HTTPException(status_code=404, detail="处理图尚未生成")
    else:
        raise HTTPException(status_code=400, detail="图片类型必须是 original 或 processed")

    path = _storage.get_local_path(key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在")

    return FileResponse(
        path=path,
        media_type=image.content_type,
        filename=image.original_filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
