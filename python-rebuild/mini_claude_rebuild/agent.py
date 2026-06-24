from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageToolCall

from .prompt import build_system_prompt
from .session import save_session
from .tools import check_permission, execute_tool, tool_definitions
from .ui import print_assistant_text, print_confirmation, print_info, print_tool_call, print_tool_result


class Agent:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "deepseek-v4-flash",
        permission_mode: str = "default",
        confirm_fn: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        self.model = model
        self.permission_mode = permission_mode
        self.confirm_fn = confirm_fn
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.system_prompt = build_system_prompt()
        self.messages: list[dict] = []
        self.session_id = uuid.uuid4().hex[:8]
        self.session_start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    async def chat(self, user_message: str) -> None:
        self.messages.append({"role": "user", "content": user_message})

        while True:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": self.system_prompt}, *self.messages],
                tools=tool_definitions,
            )

            message = response.choices[0].message
            content = message.content or ""
            if content:
                print_assistant_text(content)

            tool_calls = message.tool_calls or []
            self.messages.append(self._assistant_message(content, tool_calls))
            if not tool_calls:
                self._auto_save()
                return

            for tool_call in tool_calls:
                name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments or "{}")
                print_tool_call(name, arguments)
                permission = check_permission(name, arguments, self.permission_mode)
                if permission["action"] == "deny":
                    result = f"Action denied: {permission.get('message', '')}"
                    print_info(result)
                    self._append_tool_result(tool_call.id, result)
                    continue
                if permission["action"] == "confirm":
                    confirmed = await self._confirm_tool(permission.get("message", name))
                    if not confirmed:
                        result = "User denied this action."
                        print_info(result)
                        self._append_tool_result(tool_call.id, result)
                        continue

                result = await execute_tool(name, arguments)
                print_tool_result(name, result)
                self._append_tool_result(tool_call.id, result)

    def clear_history(self) -> None:
        self.messages.clear()
        print_info("Conversation cleared.")

    def set_confirm_fn(self, fn: Callable[[str], Awaitable[bool]]) -> None:
        self.confirm_fn = fn

    def restore_session(self, data: dict) -> None:
        messages = data.get("messages")
        if isinstance(messages, list):
            self.messages = messages
        print_info(f"Session restored ({len(self.messages)} messages).")

    def _auto_save(self) -> None:
        save_session(
            self.session_id,
            {
                "metadata": {
                    "id": self.session_id,
                    "model": self.model,
                    "cwd": str(Path.cwd()),
                    "startTime": self.session_start_time,
                    "messageCount": len(self.messages),
                },
                "messages": self.messages,
            },
        )

    async def _confirm_tool(self, message: str) -> bool:
        print_confirmation(message)
        if self.confirm_fn:
            return await self.confirm_fn(message)
        try:
            answer = input("Allow? (y/n): ")
        except EOFError:
            return False
        return answer.lower().startswith("y")

    def _append_tool_result(self, tool_call_id: str, result: str) -> None:
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
        )

    def _assistant_message(
        self,
        content: str,
        tool_calls: list[ChatCompletionMessageToolCall],
    ) -> dict:
        message: dict = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments or "{}",
                    },
                }
                for tool_call in tool_calls
            ]
        return message
