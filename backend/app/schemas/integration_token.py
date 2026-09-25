from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    scopes: set[str] = Field(min_length=1)
    expires_in_days: int = Field(default=90, ge=1, le=365)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("令牌名称不能为空白")
        return value


class TokenInfo(BaseModel):
    id: int
    name: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class TokenCreated(TokenInfo):
    token: str
