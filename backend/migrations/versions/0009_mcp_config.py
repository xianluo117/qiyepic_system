"""添加 MCP 控制台配置；初始值由应用首次启动导入。"""

import sqlalchemy as sa
from alembic import op

revision = "0009_mcp_config"
down_revision = "0008_integration_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("public_base_url", sa.String(2048), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mcp_config")
