"""控制台 MCP 设置的输入与响应。"""

from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings


class MCPConfigUpdate(BaseModel):
    enabled: bool
    public_base_url: str = Field(default="", max_length=2048)

    @model_validator(mode="after")
    def validate_address(self) -> "MCPConfigUpdate":
        value = self.public_base_url.strip()
        if not value:
            if self.enabled:
                raise ValueError("启用 MCP 前请填写公开访问地址")
            self.public_base_url = ""
            return self
        try:
            url = urlsplit(value)
            port = url.port
        except ValueError as exc:
            raise ValueError("公开访问地址格式无效") from exc
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment or url.path not in {"", "/"}
            or any(char.isspace() for char in value)
            or "\\" in value
            or port == 0
        ):
            raise ValueError("地址仅包含 http/https、域名及可选端口，不包含路径")
        if settings.app_env == "production" and url.scheme != "https":
            raise ValueError("生产环境请使用 HTTPS 公开地址")
        self.public_base_url = f"{url.scheme}://{url.netloc.lower()}"
        return self


class MCPConfigResponse(MCPConfigUpdate):
    mcp_url: str
