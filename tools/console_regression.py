"""独立 SQLite 控制台回归测试；不连接部署数据库、不写入图片。"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TEMP = tempfile.TemporaryDirectory(prefix="mcp-console-")
os.environ.update(
    DATABASE_URL_OVERRIDE="sqlite:///" + (Path(TEMP.name) / "console.db").as_posix(),
    IMAGE_ROOT=str(Path(TEMP.name) / "images"),
    APP_ENV="development",
    MCP_ENABLED="false",
    PUBLIC_BASE_URL="",
    SECRET_KEY="console-test-secret-not-for-production-123456",
    BOOTSTRAP_ADMIN_USERNAME="console-test-admin",
    BOOTSTRAP_ADMIN_PASSWORD="console-test-password-123456",
    BOOTSTRAP_ADMIN_EMPLOYEE_ID="CONSOLE_TEST",
)

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.services.mcp_config import initialize_config, read_config


class ConsoleRegression(unittest.TestCase):
    def test_console_flow(self):
        with TestClient(app) as client:
            login = client.post("/api/auth/login", data={
                "username": "console-test-admin", "password": "console-test-password-123456",
            })
            self.assertEqual(login.status_code, 200)
            admin = {"Authorization": "Bearer " + login.json()["access_token"]}
            self.assertEqual(client.get("/api/console/mcp").status_code, 401)
            with SessionLocal() as db:
                db.add(User(username="console-employee", employee_id="TEST_EMP",
                            password_hash="unused", role=UserRole.EMPLOYEE))
                db.commit()
            employee = {"Authorization": "Bearer " + create_access_token("console-employee", "employee")}
            self.assertEqual(client.get("/api/console/mcp", headers=employee).status_code, 403)
            self.assertFalse(client.get("/api/console/mcp", headers=admin).json()["enabled"])
            self.assertEqual(client.post("/mcp/").status_code, 503)
            invalid = client.put("/api/console/mcp", headers=admin, json={
                "enabled": True, "public_base_url": "http://testserver/mcp/",
            })
            self.assertEqual(invalid.status_code, 422)
            config = {"enabled": True, "public_base_url": "http://testserver"}
            response = client.put("/api/console/mcp", headers=admin, json=config)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["mcp_url"], "http://testserver/mcp/")
            with SessionLocal() as db:
                initialize_config(db)
                self.assertTrue(read_config(db).enabled)
            self.assertEqual(client.post("/mcp/").status_code, 401)
            created = client.post("/api/integration-tokens", headers=admin, json={
                "name": "console-test", "scopes": ["images:read"], "expires_in_days": 1,
            })
            self.assertEqual(created.status_code, 201)
            token_id = created.json()["id"]
            token_headers = {
                "Authorization": "Bearer " + created.json()["token"],
                "Accept": "application/json, text/event-stream",
            }
            self.assertEqual(client.get("/api/console/mcp", headers=token_headers).status_code, 401)
            initialized = client.post("/mcp/", headers=token_headers, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                           "clientInfo": {"name": "console-regression", "version": "1"}},
            })
            self.assertEqual(initialized.status_code, 200)
            self.assertIn("protocolVersion", initialized.json()["result"])
            tools = client.post("/mcp/", headers=token_headers, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            })
            self.assertEqual(tools.status_code, 200)
            self.assertEqual(len(tools.json()["result"]["tools"]), 6)
            bad_origin = client.post("/mcp/", headers={**token_headers, "Origin": "http://other.example"})
            self.assertEqual(bad_origin.status_code, 403)
            changed = {"enabled": True, "public_base_url": "http://new.example"}
            self.assertEqual(client.put("/api/console/mcp", headers=admin, json=changed).status_code, 200)
            self.assertEqual(client.post("/mcp/", headers=token_headers).status_code, 403)
            new_tools = client.post("/mcp/", headers={**token_headers, "Host": "new.example"}, json={
                "jsonrpc": "2.0", "id": 3, "method": "tools/list",
            })
            self.assertEqual(new_tools.status_code, 200)
            self.assertEqual(len(new_tools.json()["result"]["tools"]), 6)
            self.assertEqual(client.put("/api/console/mcp", headers=admin, json=config).status_code, 200)
            self.assertEqual(client.delete(f"/api/integration-tokens/{token_id}", headers=admin).status_code, 204)
            self.assertEqual(client.post("/mcp/", headers=token_headers).status_code, 401)
            self.assertEqual(client.put("/api/console/mcp", headers=admin, json={**config, "enabled": False}).status_code, 200)
            self.assertEqual(client.post("/mcp/").status_code, 503)
            self.assertEqual(client.get("/api/console/mcp", headers=admin).status_code, 200)
            settings.app_env = "production"
            try:
                self.assertEqual(client.put("/api/console/mcp", headers=admin, json=config).status_code, 422)
            finally:
                settings.app_env = "development"
        # 独立进程重新启动，验证旧环境变量不会覆盖数据库配置。
        subprocess.run([sys.executable, "-c", (
            "from fastapi.testclient import TestClient; from app.main import app; "
            "from app.core.database import SessionLocal; "
            "from app.services.mcp_config import read_config; "
            "exec('with TestClient(app):\\n with SessionLocal() as db:\\n  config = read_config(db)\\n  assert not config.enabled\\n  assert config.public_base_url == \\\"http://testserver\\\"')"
        )], check=True)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        engine.dispose()
        TEMP.cleanup()
