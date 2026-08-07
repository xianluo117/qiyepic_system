from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.image import ImageStatus


class ImageVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_id: int
    version_number: int
    ratio_width: int
    ratio_height: int
    min_short_side_px: int
    output_width: int
    output_height: int
    file_size: int
    compression_setting: str
    created_at: datetime


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
    current_version_number: int | None
    file_size: int
    content_type: str
    status: ImageStatus
    error_message: str | None
    created_at: datetime
    processed_at: datetime | None


class ImageReprocessRequest(BaseModel):
    ratio_width: int = Field(gt=0, le=1000)
    ratio_height: int = Field(gt=0, le=1000)
    min_short_side_px: int = Field(gt=0, le=20000)


class ImagePageResponse(BaseModel):
    items: list[ImageResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)


class UploadFileResult(BaseModel):
    filename: str
    success: bool
    image: ImageResponse | None = None
    error: str | None = None


class UploadResponse(BaseModel):
    results: list[UploadFileResult]
