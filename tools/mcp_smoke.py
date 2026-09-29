"""已部署 MCP 的只读冒烟测试；在 API 容器内显式执行。"""

import asyncio
import json
import os
import uuid
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


BASE_URL = os.environ.get("MCP_TEST_BASE_URL", "http://host.docker.internal:1230")
PUBLIC_URL = os.environ["PUBLIC_BASE_URL"]
API_PREFIX = os.environ.get("API_PREFIX", "/api").rstrip("/")
HEADERS = {"Host": urlsplit(PUBLIC_URL).netloc}
EXPECTED_TOOLS = {
    "upload_instructions", "search_images", "get_image",
    "get_image_links", "list_image_versions", "reprocess_image",
}


def report(name, **details):
    print(json.dumps({"check": name, **details}, ensure_ascii=True), flush=True)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def payload(result):
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    for content in result.content:
        if content.type == "text":
            return json.loads(content.text)
    raise AssertionError("Missing structured tool result")


async def check_mcp(token):
    headers = {**HEADERS, "Authorization": "Bearer " + token}
    async with streamablehttp_client(BASE_URL + "/mcp/", headers=headers) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            initialized = await session.initialize()
            report("initialize", protocol=initialized.protocolVersion,
                   server=initialized.serverInfo.name, passed=True)
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            require(names == EXPECTED_TOOLS, "Unexpected MCP tool list")
            report("tools/list", tools=sorted(names), passed=True)

            async def call(name, arguments, expected_error=None):
                result = await session.call_tool(name, arguments)
                data = payload(result)
                if expected_error is None:
                    require(not result.isError and "error" not in data,
                            name + " unexpectedly failed")
                else:
                    require(bool(result.isError), name + " missing MCP error flag")
                    require(data.get("error", {}).get("status") == expected_error,
                            name + " unexpected error status")
                report(name, passed=True, expected_error=expected_error)
                return data

            instructions = await call("upload_instructions", {})
            require(instructions["upload_path"] == API_PREFIX + "/images/upload",
                    "Unexpected upload endpoint")
            page = await call("search_images", {"page": 1, "page_size": 1})
            report("image_inventory", total=page["total"], sampled=len(page["items"]))
            await call("search_images", {"page": 0}, expected_error=422)
            await call("get_image", {"image_id": -1}, expected_error=404)
            await call("get_image_links", {"image_id": -1}, expected_error=404)
            await call("list_image_versions", {"image_id": -1}, expected_error=404)
            if page["items"]:
                image_id = page["items"][0]["id"]
                await call("get_image", {"image_id": image_id})
                await call("list_image_versions", {"image_id": image_id})
                links = await call("get_image_links", {"image_id": image_id})
                # 仅核对链接结构，不读取图片内容或触发缩略图生成。
                for link in links.values():
                    if link:
                        require(link.startswith(PUBLIC_URL.rstrip("/") + "/"),
                                "Unexpected public image URL")
                report("public_link_structure", passed=True)
            else:
                report("existing_image_queries", skipped="No existing images")


async def main():
    token_id = None
    token = None
    admin_headers = None
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS,
                                 timeout=20, follow_redirects=False) as client:
        response = await client.get("/health")
        require(response.status_code == 200, "Health check failed")
        report("host_port_nginx_health", passed=True)
        for label, auth in [("missing_token", {}),
                            ("invalid_token", {"Authorization": "Bearer invalid-smoke-token"})]:
            response = await client.post("/mcp/", headers=auth, json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            require(response.status_code == 401, label + " must return 401")
            report(label, status=response.status_code, passed=True)

        response = await client.post(API_PREFIX + "/auth/login", data={
            "username": os.environ["BOOTSTRAP_ADMIN_USERNAME"],
            "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"],
        })
        require(response.status_code == 200, "Configured bootstrap admin login failed")
        admin_headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        try:
            response = await client.post(API_PREFIX + "/integration-tokens",
                                         headers=admin_headers, json={
                "name": "mcp-smoke-" + uuid.uuid4().hex[:12],
                "scopes": ["images:read"], "expires_in_days": 1,
            })
            require(response.status_code == 201, "Temporary token creation failed")
            created = response.json()
            token_id, token = created["id"], created["token"]
            report("temporary_readonly_token", id=token_id, passed=True)
            await check_mcp(token)
        finally:
            if token_id is not None:
                response = await client.delete(
                    API_PREFIX + "/integration-tokens/" + str(token_id), headers=admin_headers)
                require(response.status_code == 204,
                        "CRITICAL: temporary token revocation failed; revoke ID " + str(token_id))
                report("revoke_temporary_token", id=token_id, passed=True)
                response = await client.post("/mcp/", headers={
                    "Authorization": "Bearer " + token,
                }, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
                require(response.status_code == 401, "Revoked token was not rejected")
                report("revoked_token_rejected", status=response.status_code, passed=True)
    report("summary", passed=True, image_writes=0)


if __name__ == "__main__":
    asyncio.run(main())
