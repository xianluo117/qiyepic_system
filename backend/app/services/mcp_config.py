"""MCP 配置持久化，不使用进程内缓存。"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.mcp_config import MCPConfig
from app.schemas.mcp_config import MCPConfigResponse, MCPConfigUpdate


def initialize_config(db: Session) -> None:
    if db.get(MCPConfig, 1) is not None:
        return
    try:
        initial = MCPConfigUpdate(
            enabled=settings.mcp_enabled, public_base_url=settings.public_base_url,
        )
    except ValueError:
        # 旧环境配置无效时仍允许启动控制台进行修正。
        initial = MCPConfigUpdate(enabled=False, public_base_url="")
    db.add(MCPConfig(id=1, **initial.model_dump()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(MCPConfig, 1) is None:
            raise


def read_config(db: Session) -> MCPConfigResponse:
    record = db.get(MCPConfig, 1)
    if record is None:
        raise RuntimeError("MCP 配置尚未初始化")
    return MCPConfigResponse(
        enabled=record.enabled, public_base_url=record.public_base_url,
        mcp_url=record.public_base_url + "/mcp/" if record.public_base_url else "",
    )


def save_config(db: Session, payload: MCPConfigUpdate) -> MCPConfigResponse:
    record = db.get(MCPConfig, 1)
    if record is None:
        raise RuntimeError("MCP 配置尚未初始化")
    record.enabled = payload.enabled
    record.public_base_url = payload.public_base_url
    db.commit()
    return read_config(db)
