from __future__ import annotations

import json

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageToolCall

from .prompt import build_system_prompt
from .tools import execute_tool, tool_definitions
from .ui import print_assistant_text, print_tool_call, print_tool_result


class Agent:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "deepseek-v4-flash",
    ) -> None:
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.system_prompt = build_system_prompt()
        self.messages: list[dict] = []

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
                return

            for tool_call in tool_calls:
                name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments or "{}")
                print_tool_call(name, arguments)
                result = await execute_tool(name, arguments)
                print_tool_result(name, result)
                self.messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
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
