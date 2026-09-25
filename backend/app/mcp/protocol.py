"""MCP 返回适配：业务错误使用协议级 isError 标记。"""

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult


class ImageMCP(FastMCP):
    async def call_tool(self, name, arguments):
        result = await super().call_tool(name, arguments)
        # FastMCP 的结构化工具返回 (content, structured_content)。
        if isinstance(result, tuple) and len(result) == 2:
            content, structured = result
            if isinstance(structured, dict) and "error" in structured:
                return CallToolResult(
                    content=content, structuredContent=structured, isError=True,
                )
        return result
