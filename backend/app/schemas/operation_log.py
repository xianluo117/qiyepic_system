from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.operation_log import LogCategory, LogStatus


class OperationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: LogCategory
    action: str
    status: LogStatus
    actor_username: str | None
    employee_id: str | None
    image_id: int | None
    target: str | None
    message: str
    details: str | None
    created_at: datetime
