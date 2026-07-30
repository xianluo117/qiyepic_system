from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "简易图床系统"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api"

    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = 480

    database_url_override: str | None = None
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "image_system"
    mysql_user: str = "image_system"
    mysql_password: str = ""

    redis_url: str = "redis://127.0.0.1:6379/0"
    task_always_eager: bool = False
    image_root: Path = Path("/data/image-system")
    max_upload_size_mb: int = 30
    allowed_image_formats: tuple[str, ...] = ("JPEG", "PNG", "WEBP")
    bootstrap_admin_username: str = Field(min_length=3, max_length=128)
    bootstrap_admin_password: str = Field(min_length=12, max_length=128)
    bootstrap_admin_employee_id: str = Field(min_length=1, max_length=64)

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            "mysql+pymysql://"
            f"{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
