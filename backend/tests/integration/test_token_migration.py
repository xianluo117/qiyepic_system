"""集成令牌迁移的独立升降级验证。"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_token_migration(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "migrations/versions/0008_integration_tokens.py"
    spec = importlib.util.spec_from_file_location("token_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            inspector = sa.inspect(connection)
            assert "integration_tokens" in inspector.get_table_names()
            unique = inspector.get_unique_constraints("integration_tokens")
            assert any(item["column_names"] == ["token_hash"] for item in unique)
            migration.downgrade()
            assert "integration_tokens" not in sa.inspect(connection).get_table_names()
    finally:
        engine.dispose()
