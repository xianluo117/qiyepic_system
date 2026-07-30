from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.image import ImageStatus


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: str
    sku: str
    original_filename: str
    target_ratio_width: int
    target_ratio_height: int
    min_short_side_px: int
    original_width: int | None
    original_height: int | None
    processed_width: int | None
    processed_height: int | None
    file_size: int
    content_type: str
    status: ImageStatus
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None


class UploadFileResult(BaseModel):
    filename: str
    success: bool
    image: ImageResponse | None = None
    error: str | None = None


class UploadResponse(BaseModel):
    results: list[UploadFileResult]
