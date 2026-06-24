from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Awaitable, Callable

import anthropic
from openai import AsyncOpenAI

from .prompt import build_system_prompt
from .session import save_session
from .tools import check_permission, execute_tool, tool_definitions
from .ui import print_assistant_delta, print_confirmation, print_info, print_tool_call, print_tool_result

LARGE_RESULT_THRESHOLD = 30 * 1024
KEEP_RECENT_TOOL_RESULTS = 3
SNIP_PLACEHOLDER = "[Content snipped - re-read if needed]"
SUMMARY_SYSTEM_PROMPT = "You are a conversation summarizer. Be concise but preserve important details."
SUMMARY_USER_PROMPT = (
    "Summarize the conversation so far in a concise paragraph. "
    "Preserve key decisions, file paths, user preferences, and context needed to continue the work."
)


class Agent:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None,
        model: str = "deepseek-v4-flash",
        use_openai: bool = True,
        permission_mode: str = "default",
        confirm_fn: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        self.model = model
        self.use_openai = use_openai
        self.permission_mode = permission_mode
        self.confirm_fn = confirm_fn
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url) if use_openai else None
        self.anthropic_client = (
            None
            if use_openai
            else anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        )
        self.system_prompt = build_system_prompt()
        self.messages: list[dict] = []
        self.session_id = uuid.uuid4().hex[:8]
        self.session_start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    async def chat(self, user_message: str) -> None:
        self.messages.append({"role": "user", "content": user_message})

        while True:
            message = await self._call_openai_stream() if self.use_openai else await self._call_anthropic_stream()
            content = message["content"]
            tool_calls = message["tool_calls"]
            self.messages.append(self._assistant_message(content, tool_calls))
            if not tool_calls:
                self._auto_save()
                return

            for tool_call in tool_calls:
                name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"] or "{}")
                print_tool_call(name, arguments)
                permission = check_permission(name, arguments, self.permission_mode)
                if permission["action"] == "deny":
                    result = f"Action denied: {permission.get('message', '')}"
                    print_info(result)
                    self._append_tool_result(tool_call["id"], result)
                    continue
                if permission["action"] == "confirm":
                    confirmed = await self._confirm_tool(permission.get("message", name))
                    if not confirmed:
                        result = "User denied this action."
                        print_info(result)
                        self._append_tool_result(tool_call["id"], result)
                        continue

                result = await execute_tool(name, arguments)
                result = self._persist_large_result(name, result)
                print_tool_result(name, result)
                self._append_tool_result(tool_call["id"], result)
                self._run_compression_pipeline()

    def clear_history(self) -> None:
        self.messages.clear()
        print_info("Conversation cleared.")

    def set_confirm_fn(self, fn: Callable[[str], Awaitable[bool]]) -> None:
        self.confirm_fn = fn

    async def compact(self) -> None:
        if len(self.messages) < 2:
            print_info("Nothing to compact yet.")
            return

        summary = await self._summarize_messages()
        self.messages = [
            {"role": "user", "content": f"[Previous conversation summary]\n{summary}"},
            {
                "role": "assistant",
                "content": "Understood. I have the context from our previous conversation.",
            },
        ]
        self._auto_save()
        print_info("Conversation compacted.")

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
                    "backend": "openai-compatible" if self.use_openai else "anthropic",
                    "cwd": str(Path.cwd()),
                    "startTime": self.session_start_time,
                    "messageCount": len(self.messages),
                },
                "messages": self.messages,
            },
        )

    def _persist_large_result(self, tool_name: str, result: str) -> str:
        if len(result.encode("utf-8")) <= LARGE_RESULT_THRESHOLD:
            return result

        output_dir = Path.home() / ".mini-claude-rebuild" / "tool-results"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{int(time.time() * 1000)}-{tool_name}.txt"
        path.write_text(result, encoding="utf-8")

        lines = result.splitlines()
        preview = "\n".join(lines[:200])
        size_kb = len(result.encode("utf-8")) / 1024
        return (
            f"[Result too large ({size_kb:.1f} KB, {len(lines)} lines). "
            f"Full output saved to {path}. Use read_file to inspect it later.]\n\n"
            f"Preview (first 200 lines):\n{preview}"
        )

    def _run_compression_pipeline(self) -> None:
        tool_message_indexes = [
            index
            for index, message in enumerate(self.messages)
            if message.get("role") == "tool"
            and isinstance(message.get("content"), str)
            and message["content"] != SNIP_PLACEHOLDER
        ]
        old_tool_messages = tool_message_indexes[:-KEEP_RECENT_TOOL_RESULTS]
        for index in old_tool_messages:
            self.messages[index]["content"] = SNIP_PLACEHOLDER

    async def _summarize_messages(self) -> str:
        history = self._messages_as_summary_text()
        if self.use_openai:
            if self.client is None:
                raise RuntimeError("OpenAI-compatible client is not configured.")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{history}\n\n{SUMMARY_USER_PROMPT}"},
                ],
            )
            return response.choices[0].message.content or "No summary available."

        if self.anthropic_client is None:
            raise RuntimeError("Anthropic client is not configured.")
        response = await self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"{history}\n\n{SUMMARY_USER_PROMPT}"}],
        )
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ) or "No summary available."

    def _messages_as_summary_text(self) -> str:
        lines: list[str] = []
        for message in self.messages:
            role = message.get("role", "unknown")
            if role == "assistant" and message.get("tool_calls"):
                tool_names = [tool_call["function"]["name"] for tool_call in message["tool_calls"]]
                lines.append(f"assistant tool calls: {', '.join(tool_names)}")
            content = message.get("content")
            if isinstance(content, str) and content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

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

    async def _call_openai_stream(self) -> dict:
        if self.client is None:
            raise RuntimeError("OpenAI-compatible client is not configured.")

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": self.system_prompt}, *self.messages],
            tools=tool_definitions,
            stream=True,
        )

        content = ""
        tool_calls_by_index: dict[int, dict] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if delta.content:
                print_assistant_delta(delta.content)
                content += delta.content

            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    index = tool_call_delta.index
                    current = tool_calls_by_index.setdefault(
                        index,
                        {
                            "id": tool_call_delta.id or f"call_{index}",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if tool_call_delta.id:
                        current["id"] = tool_call_delta.id
                    if tool_call_delta.function and tool_call_delta.function.name:
                        current["function"]["name"] += tool_call_delta.function.name
                    if tool_call_delta.function and tool_call_delta.function.arguments:
                        current["function"]["arguments"] += tool_call_delta.function.arguments

        if content and not content.endswith("\n"):
            print()

        tool_calls = [tool_call for _, tool_call in sorted(tool_calls_by_index.items())]
        return {"content": content, "tool_calls": tool_calls}

    async def _call_anthropic_stream(self) -> dict:
        if self.anthropic_client is None:
            raise RuntimeError("Anthropic client is not configured.")

        tool_calls_by_index: dict[int, dict] = {}
        content = ""

        async with self.anthropic_client.messages.stream(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=self._to_anthropic_messages(),
            tools=self._to_anthropic_tools(),
        ) as stream:
            async for event in stream:
                event_type = getattr(event, "type", "")
                if event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if getattr(block, "type", None) == "tool_use":
                        tool_calls_by_index[event.index] = {
                            "id": block.id,
                            "type": "function",
                            "function": {"name": block.name, "arguments": ""},
                        }
                elif event_type == "content_block_delta":
                    delta = event.delta
                    text = getattr(delta, "text", None)
                    if text:
                        print_assistant_delta(text)
                        content += text

                    partial_json = getattr(delta, "partial_json", None)
                    if partial_json:
                        current = tool_calls_by_index.setdefault(
                            event.index,
                            {
                                "id": f"toolu_{event.index}",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        current["function"]["arguments"] += partial_json

            final_message = await stream.get_final_message()

        if content and not content.endswith("\n"):
            print()

        tool_calls = self._anthropic_tool_calls_from_final_message(final_message, tool_calls_by_index)
        return {"content": content, "tool_calls": tool_calls}

    def _to_anthropic_tools(self) -> list[dict]:
        return [
            {
                "name": tool["function"]["name"],
                "description": tool["function"].get("description", ""),
                "input_schema": tool["function"]["parameters"],
            }
            for tool in tool_definitions
        ]

    def _to_anthropic_messages(self) -> list[dict]:
        converted: list[dict] = []
        for message in self.messages:
            role = message["role"]
            if role == "user":
                converted.append({"role": "user", "content": message["content"]})
            elif role == "assistant":
                content_blocks: list[dict] = []
                if message.get("content"):
                    content_blocks.append({"type": "text", "text": message["content"]})
                for tool_call in message.get("tool_calls") or []:
                    arguments = tool_call["function"].get("arguments") or "{}"
                    try:
                        tool_input = json.loads(arguments)
                    except json.JSONDecodeError:
                        tool_input = {}
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tool_call["id"],
                            "name": tool_call["function"]["name"],
                            "input": tool_input,
                        }
                    )
                converted.append({"role": "assistant", "content": content_blocks or ""})
            elif role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message["tool_call_id"],
                                "content": message["content"],
                            }
                        ],
                    }
                )
        return converted

    def _anthropic_tool_calls_from_final_message(
        self,
        final_message: object,
        streamed_tool_calls: dict[int, dict],
    ) -> list[dict]:
        tool_calls: list[dict] = []
        for block in getattr(final_message, "content", []) or []:
            if getattr(block, "type", None) != "tool_use":
                continue
            tool_calls.append(
                {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input or {}),
                    },
                }
            )

        if tool_calls:
            return tool_calls

        for _, tool_call in sorted(streamed_tool_calls.items()):
            tool_call["function"]["arguments"] = tool_call["function"]["arguments"] or "{}"
            tool_calls.append(tool_call)
        return tool_calls

    def _assistant_message(
        self,
        content: str,
        tool_calls: list[dict],
    ) -> dict:
        message: dict = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return message
