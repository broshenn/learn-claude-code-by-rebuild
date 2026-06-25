from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any


class McpConnection:
    """One stdio MCP server connection using newline-delimited JSON-RPC."""

    def __init__(
        self,
        server_name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.process: asyncio.subprocess.Process | None = None
        self.next_id = 1
        self.pending: dict[int, asyncio.Future] = {}
        self.reader_task: asyncio.Task | None = None

    async def connect(self) -> None:
        merged_env = {**os.environ, **self.env}
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
        )
        self.reader_task = asyncio.create_task(self._read_loop())

    async def initialize(self) -> None:
        await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mini-claude-rebuild", "version": "0.1.0"},
            },
        )
        self._send_notification("notifications/initialized")

    async def list_tools(self) -> list[dict]:
        result = await self._send_request("tools/list")
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "inputSchema": tool.get("inputSchema"),
                "serverName": self.server_name,
            }
            for tool in tools
            if isinstance(tool, dict) and "name" in tool
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self._send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        if isinstance(result, dict) and isinstance(result.get("content"), list):
            texts = [
                part.get("text", "")
                for part in result["content"]
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            return "\n".join(texts)
        return json.dumps(result, ensure_ascii=False)

    async def _read_loop(self) -> None:
        if not self.process or not self.process.stdout:
            return

        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            message_id = message.get("id")
            if message_id not in self.pending:
                continue

            future = self.pending.pop(message_id)
            if "error" in message:
                error = message["error"]
                future.set_exception(
                    RuntimeError(f"MCP error {error.get('code')}: {error.get('message')}")
                )
            else:
                future.set_result(message.get("result"))

    async def _send_request(self, method: str, params: dict | None = None) -> Any:
        if not self.process or not self.process.stdin:
            raise RuntimeError(f"MCP server '{self.server_name}' is not connected")

        request_id = self.next_id
        self.next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self.pending[request_id] = future

        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        self.process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        await self.process.stdin.drain()
        return await future

    def _send_notification(self, method: str, params: dict | None = None) -> None:
        if not self.process or not self.process.stdin:
            return
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self.process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))

    def close(self) -> None:
        if self.reader_task:
            self.reader_task.cancel()
            self.reader_task = None
        if self.process:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
            self.process = None
        for future in self.pending.values():
            if not future.done():
                future.set_exception(RuntimeError(f"MCP server '{self.server_name}' closed"))
        self.pending.clear()

    async def disconnect(self) -> None:
        process = self.process
        reader_task = self.reader_task
        self.close()

        if process:
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except (asyncio.TimeoutError, ProcessLookupError):
                pass
        if reader_task:
            try:
                await reader_task
            except asyncio.CancelledError:
                pass


class McpManager:
    """Load MCP server config, discover tools, and route prefixed tool calls."""

    def __init__(self) -> None:
        self.connections: dict[str, McpConnection] = {}
        self.tools: list[dict] = []
        self.connected = False

    async def load_and_connect(self) -> None:
        if self.connected:
            return
        self.connected = True

        for name, config in self._load_configs().items():
            connection = McpConnection(
                name,
                config["command"],
                config.get("args"),
                config.get("env"),
            )
            try:
                await connection.connect()
                await asyncio.wait_for(connection.initialize(), timeout=15)
                server_tools = await asyncio.wait_for(connection.list_tools(), timeout=15)
            except Exception as exc:
                print(f"[mcp] Failed to connect to '{name}': {exc}", flush=True)
                await connection.disconnect()
                continue

            self.connections[name] = connection
            self.tools.extend(server_tools)
            print(f"[mcp] Connected to '{name}' - {len(server_tools)} tools", flush=True)

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": f"mcp__{tool['serverName']}__{tool['name']}",
                    "description": tool.get("description")
                    or f"MCP tool {tool['name']} from {tool['serverName']}",
                    "parameters": tool.get("inputSchema")
                    or {"type": "object", "properties": {}},
                },
            }
            for tool in self.tools
        ]

    def is_mcp_tool(self, name: str) -> bool:
        return name.startswith("mcp__")

    async def call_tool(self, prefixed_name: str, arguments: dict) -> str:
        parts = prefixed_name.split("__")
        if len(parts) < 3:
            raise ValueError(f"Invalid MCP tool name: {prefixed_name}")

        server_name = parts[1]
        tool_name = "__".join(parts[2:])
        connection = self.connections.get(server_name)
        if not connection:
            raise RuntimeError(f"MCP server '{server_name}' is not connected")
        return await connection.call_tool(tool_name, arguments)

    async def disconnect_all(self) -> None:
        for connection in self.connections.values():
            await connection.disconnect()
        self.connections.clear()
        self.tools.clear()
        self.connected = False

    def _load_configs(self) -> dict[str, dict]:
        merged: dict[str, dict] = {}
        for path in [
            Path.home() / ".claude" / "settings.json",
            Path.cwd() / ".claude" / "settings.json",
            Path.cwd() / ".mcp.json",
        ]:
            self._merge_config_file(path, merged)
        return merged

    def _merge_config_file(self, path: Path, target: dict[str, dict]) -> None:
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return

        servers = raw.get("mcpServers", {})
        if not isinstance(servers, dict):
            return

        for name, config in servers.items():
            if isinstance(config, dict) and isinstance(config.get("command"), str):
                target[name] = config
