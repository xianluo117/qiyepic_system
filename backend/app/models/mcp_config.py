"""控制台维护的 MCP 运行配置。"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MCPConfig(Base):
    __tablename__ = "mcp_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_base_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
