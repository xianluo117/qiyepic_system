"""管理员 MCP 控制台配置接口。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.schemas.mcp_config import MCPConfigResponse, MCPConfigUpdate
from app.services.mcp_config import read_config, save_config

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/mcp", response_model=MCPConfigResponse)
def get_mcp_config(db: Session = Depends(get_db)) -> MCPConfigResponse:
    return read_config(db)


@router.put("/mcp", response_model=MCPConfigResponse)
def update_mcp_config(
    payload: MCPConfigUpdate, db: Session = Depends(get_db),
) -> MCPConfigResponse:
    return save_config(db, payload)
