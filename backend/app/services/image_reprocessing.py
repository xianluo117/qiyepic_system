"""图片重新处理的共用业务服务。"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.image import Image, ImageStatus
from app.models.operation_log import LogCategory, LogStatus
from app.models.user import User, UserRole
from app.processing.paths import get_processed_filename
from app.schemas.image import ImageReprocessRequest
from app.services.audit import add_operation_log
from app.services.integration_images import accessible_image
from app.storage.local import LocalStorage
from worker.tasks.image_tasks import process_image


def reprocess(
    db: Session, user: User, image_id: int, payload: ImageReprocessRequest,
) -> Image:
    image = accessible_image(db, user, image_id)
    if user.role != UserRole.ADMIN and image.owner_id != user.id:
        raise HTTPException(status_code=403, detail="只能修改自己上传的图片")
    if image.status in {ImageStatus.PENDING, ImageStatus.PROCESSING}:
        raise HTTPException(status_code=409, detail="图片任务正在处理中")
    storage = LocalStorage(settings.image_root)
    if image.current_version_number is None:
        for filename in {get_processed_filename(image.original_filename), image.original_filename}:
            key = storage.build_key(image.employee_id, "processed", image.sku, filename)
            if key != image.processed_path:
                path = storage.get_local_path(key)
                path.unlink(missing_ok=True)
                path.with_name(f".{path.name}.processing").unlink(missing_ok=True)
    image.target_ratio_width = payload.ratio_width
    image.target_ratio_height = payload.ratio_height
    image.min_short_side_px = payload.min_short_side_px
    image.status = ImageStatus.PENDING
    image.error_message = None
    add_operation_log(
        db, category=LogCategory.PROCESSING, action="retry_image", status=LogStatus.INFO,
        actor=user, image_id=image.id, target=f"{image.sku}/{image.original_filename}",
        message=f"重新提交图片处理任务 {image.original_filename}",
        details=f"ratio={payload.ratio_width}:{payload.ratio_height}, "
                f"min_short_side={payload.min_short_side_px}",
    )
    db.commit()
    try:
        process_image.delay(image.id)
    except Exception as exc:
        image.status = ImageStatus.FAILED
        image.error_message = f"处理任务提交失败: {exc}"[:2000]
        add_operation_log(
            db, category=LogCategory.PROCESSING, action="enqueue_image", status=LogStatus.FAILED,
            actor=user, image_id=image.id, target=f"{image.sku}/{image.original_filename}",
            message="无法提交图片重试任务", details=str(exc),
        )
        db.commit()
    db.refresh(image)
    return image
