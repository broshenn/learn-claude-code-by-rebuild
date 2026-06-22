from __future__ import annotations

import json

from openai import AsyncOpenAI

from .tools import execute_tool, tool_definitions


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
        self.messages: list[dict[str, str]] = []

    async def chat(self, user_message: str) -> None:
        self.messages.append({"role": "user", "content": user_message})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=tool_definitions,
        )

        message = response.choices[0].message
        content = message.content or ""
        if content:
            print(content)

        tool_calls = message.tool_calls or []
        if not tool_calls:
            self.messages.append({"role": "assistant", "content": content})
            return

        for tool_call in tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")
            result = await execute_tool(name, arguments)
            print(f"\n[tool:{name}]")
            print(result)
