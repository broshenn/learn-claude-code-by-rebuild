# 🎯 从零重搭 Python Mini Claude Code：增量式写代码章节规划

这份规划的目标是：不直接复制当前源码，而是新建一个干净项目，从最小可运行代码开始，一章一章加功能。每一章结束时，代码都能运行；每往后一章，代码只增加必要能力，直到逐步过渡成当前 `python/mini_claude` 的完整形态。

> 💡 一句话路线：先做一个只能聊天的 CLI，再让它会读文件、会调用工具、会循环、会改代码、会保存会话、会加载规则，最后补齐记忆、技能、子 Agent、MCP、权限和上下文压缩。

---

## 0. 最终目标代码结构

最终要过渡到这套结构：

```text
python/
  pyproject.toml
  mini_claude_rebuild/
    __init__.py
    __main__.py
    agent.py
    tools.py
    ui.py
    prompt.py
    session.py
    frontmatter.py
    memory.py
    skills.py
    subagent.py
    mcp_client.py
```

但是一开始不要全建。每章只建当章真正需要的文件。

---

## 1. 章节总表：每章代码怎么变多

| 章 | 版本目标 | 本章新增/扩展文件 | 结束时能做什么 |
|----|----------|------------------|----------------|
| 1 | 空项目变 CLI | `pyproject.toml`、`__main__.py`、`__init__.py` | 能运行 `mini-claude-rebuild --help` |
| 2 | 普通聊天机器人 | `agent.py`、扩展 `__main__.py` | 能把用户输入发给模型并打印回答 |
| 3 | 最小工具调用 | `tools.py`、扩展 `agent.py` | 模型能调用 `read_file` |
| 4 | Agent Loop 闭环 | 扩展 `agent.py` | 能 `tool_use -> tool_result -> 再问模型` |
| 5 | 基础文件工具 | 扩展 `tools.py` | 能读、列、搜文件 |
| 6 | 修改文件能力 | 扩展 `tools.py` | 能写文件、精确编辑文件 |
| 7 | Shell 与验证 | 扩展 `tools.py` | 能运行测试、构建、命令 |
| 8 | 终端体验 | `ui.py`、扩展 `agent.py` | 工具调用、错误、费用显示更清晰 |
| 9 | System Prompt | `prompt.py` | 能加载项目规则和环境上下文 |
| 10 | REPL | 扩展 `__main__.py` | 支持交互式对话和 `/clear` |
| 11 | 会话持久化 | `session.py` | 支持 `--resume` |
| 12 | 权限系统 | 扩展 `tools.py`、`agent.py` | 不同模式控制写文件和 shell |
| 13 | 流式输出 | 扩展 `agent.py` | 模型边生成边显示 |
| 14 | 补 Anthropic 后端 | 扩展 `agent.py`、`__main__.py` | 从 DeepSeek/OpenAI 兼容路径扩展到双后端 |
| 15 | 上下文压缩 | 扩展 `agent.py` | 长对话不容易爆上下文 |
| 16 | Frontmatter | `frontmatter.py` | 能解析 `--- metadata ---` |
| 17 | 记忆系统 | `memory.py`、扩展 `prompt.py` | 能保存和召回长期记忆 |
| 18 | 技能系统 | `skills.py`、扩展 `prompt.py`、`__main__.py` | 能发现和调用 `SKILL.md` |
| 19 | Plan Mode | 扩展 `agent.py`、`tools.py`、`ui.py` | 能先规划再执行 |
| 20 | 子 Agent | `subagent.py`、扩展 `agent.py` | 能启动隔离上下文的子 Agent |
| 21 | MCP | `mcp_client.py`、扩展 `agent.py` | 能连接外部 MCP 工具 |
| 22 | 最终对齐 | 全部文件打磨 | 行为接近当前源码 |

---

## 2. 第 1 章：创建最小 Python CLI 项目

### 本章目标

只解决一件事：这个项目能作为 Python 包安装，并能通过命令行启动。

### 本章代码结构

```text
python/
  pyproject.toml
  mini_claude_rebuild/
    __init__.py
    __main__.py
```

### 本章要写的代码

`pyproject.toml`：

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "claude-code-from-scratch"
version = "0.1.0"
description = "A minimal coding agent built from scratch in Python"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
mini-claude-rebuild = "mini_claude_rebuild.__main__:main"

[tool.setuptools.packages.find]
include = ["mini_claude_rebuild*"]
```

`mini_claude_rebuild/__main__.py`：

```python
def main() -> None:
    print("Mini Claude Python is running.")


if __name__ == "__main__":
    main()
```

### 验收命令

```bash
cd python-rebuild
pip install -e .
mini-claude-rebuild
python -m mini_claude_rebuild
```

### 过渡到源码

当前项目最终版的 `__main__.py` 很长，但它的根仍然是这一章的 `main()`。后面每章都往这个入口里加参数、REPL、session、plan mode。

---

## 3. 第 2 章：接入模型，做普通聊天

### 本章目标

先不做工具，也不做 Agent Loop，只实现“用户输入 -> 模型回答”。

### 本章新增文件

```text
mini_claude_rebuild/
  agent.py
```

### 本章扩展依赖

`pyproject.toml` 加：

```toml
dependencies = [
    "openai>=1.50.0",
    "python-dotenv>=1.0.0",
]
```

### 本章要写的核心代码

`agent.py`：

```python
from __future__ import annotations

from openai import AsyncOpenAI


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
        )
        message = response.choices[0].message
        content = message.content or ""
        self.messages.append({"role": "assistant", "content": content})
        print(content)
```

`__main__.py` 扩展为：

```python
import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from .agent import Agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="*")
    parser.add_argument("--model", default=None)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY is required. Put it in .env or set it in your shell.")
        sys.exit(1)
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = args.model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    prompt = " ".join(args.prompt) or "hello"
    agent = Agent(api_key=api_key, base_url=base_url, model=model)
    asyncio.run(agent.chat(prompt))
```

### 验收命令

```bash
mini-claude-rebuild "hello"
```

### 过渡到源码

这一章对应最终 `agent.py` 的最早形态。我们的重建路线先用 DeepSeek 的 OpenAI 兼容接口跑通聊天，后面再补 Anthropic 后端，把 `chat()` 逐步拆成不同后端分支。

---

## 4. 第 3 章：加入第一个工具 read_file

### 本章目标

让模型不再只能“凭空回答”，而是能请求读取真实文件。

### 本章新增文件

```text
mini_claude_rebuild/
  tools.py
```

### 本章要写的工具定义

`tools.py`：

```python
from pathlib import Path


tool_definitions = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file with line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                },
                "required": ["file_path"],
            },
        },
    }
]


def read_file(file_path: str) -> str:
    content = Path(file_path).read_text(encoding="utf-8")
    lines = content.splitlines()
    return "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))


async def execute_tool(name: str, inp: dict) -> str:
    if name == "read_file":
        return read_file(inp["file_path"])
    return f"Unknown tool: {name}"
```

### `agent.py` 本章要改什么

调用模型时传入 tools：

```python
from .tools import tool_definitions, execute_tool
```

然后在 `messages.create()` 中加：

```python
tools=tool_definitions,
```

### 本章先不做完整循环

这一章只需要看到模型返回 `tool_calls`，然后把工具结果打印出来即可：

```python
for tool_call in message.tool_calls or []:
    name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments or "{}")
    result = await execute_tool(name, arguments)
    print(result)
```

### 验收命令

```bash
mini-claude-rebuild "Read pyproject.toml"
```

预期：模型调用 `read_file`，终端能显示文件内容。

### 过渡到源码

最终 `tools.py` 的核心仍然是三件事：`tool_definitions`、工具函数、`execute_tool()` 分发。

---

## 5. 第 4 章：完成真正的 Agent Loop

### 本章目标

把第 3 章“工具结果只打印”升级为真正闭环：工具结果必须喂回模型，让模型基于真实文件内容继续回答。

### 本章重点逻辑

```text
while True:
    调模型
    如果没有 tool_use:
        break
    执行 tool_use
    追加 tool_result
    下一轮继续
```

### `agent.py` 增量改法

把 `chat()` 改成循环：

```python
async def chat(self, user_message: str) -> None:
    self.messages.append({"role": "user", "content": user_message})

    while True:
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
        self.messages.append(assistant_message(content, tool_calls))
        if not tool_calls:
            break

        for tool_call in tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")
            result = await execute_tool(name, arguments)
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
```

### 验收命令

```bash
mini-claude-rebuild "Read pyproject.toml and tell me the package name."
```

预期：模型先读文件，再根据工具结果回答，不只是打印文件内容。

### 过渡到源码

这一章就是整个项目的心脏。后续所有功能都是围绕这个循环加保护、加能力、加体验。

---

## 6. 第 5 章：加入 list_files 和 grep_search

### 本章目标

让 Agent 能自己探索项目，不必用户告诉它每个文件路径。

### 本章扩展 `tools.py`

新增工具：

```text
list_files(pattern, path=".")
grep_search(pattern, path=".", include=None)
```

### 本章实现要点

| 工具 | 实现方式 |
|------|----------|
| `list_files` | `Path(path).glob(pattern)` |
| `grep_search` | 遍历文件，用 `re.search()` 匹配 |

### 本章验收

```bash
mini-claude-rebuild "Find where the Agent class is defined."
mini-claude-rebuild "List all Python files under mini_claude_rebuild."
```

### 过渡到源码

最终源码里的 `grep_search` 会更完整：能调用系统搜索工具，失败后回退 Python 实现，并支持 include glob。

---

## 7. 第 6 章：加入 write_file 和 edit_file

### 本章目标

Agent 开始具备“改代码”的能力。

### 本章扩展工具

```text
write_file(file_path, content)
edit_file(file_path, old_string, new_string)
```

### 实现顺序

1. `write_file`：先直接覆盖写入。
2. `edit_file`：读取文件，检查 `old_string` 是否存在。
3. 如果 `old_string` 出现 0 次，返回错误。
4. 如果出现多次，返回错误，要求模型提供更精确片段。
5. 只出现 1 次时替换。
6. 返回修改成功和简单 diff。

### 验收命令

```bash
mini-claude-rebuild "Create tmp_demo.txt with the text hello."
mini-claude-rebuild "Edit tmp_demo.txt and change hello to hello mini claude."
```

### 过渡到源码

最终源码会加上 quote normalization、mtime 保护、读前编辑保护、diff 展示和 memory index 自动更新。

---

## 8. 第 7 章：加入 run_shell

### 本章目标

让 Agent 能运行测试、安装命令、查看 git 状态。

### 本章扩展工具

```text
run_shell(command, timeout=30000)
```

### 实现要点

1. 使用 `subprocess.run()`。
2. 捕获 stdout、stderr、exit code。
3. 支持超时。
4. 先不做权限确认，下一章再做。

### 验收命令

```bash
mini-claude-rebuild "Run python --version and tell me the result."
mini-claude-rebuild "Run git status --short."
```

### 过渡到源码

最终源码会按 Windows/macOS/Linux 区分 shell，并加入危险命令检测。

---

## 9. 第 8 章：抽出 ui.py，改善输出体验

### 本章目标

代码开始模块化：Agent 不直接 `print()` 所有内容，而是交给 `ui.py`。

### 本章新增文件

```text
mini_claude_rebuild/
  ui.py
```

### 本章实现函数

```python
def print_welcome() -> None: ...
def print_user_prompt() -> None: ...
def print_assistant_text(text: str) -> None: ...
def print_tool_call(name: str, inp: dict) -> None: ...
def print_tool_result(name: str, result: str) -> None: ...
def print_error(msg: str) -> None: ...
def print_info(msg: str) -> None: ...
```

### 本章验收

执行任意读文件任务，终端能看出：

```text
assistant 正在说什么
调用了哪个工具
工具返回了什么摘要
```

### 过渡到源码

最终 `ui.py` 会使用 Rich，并加入 spinner、plan approval、sub-agent start/end、费用显示。

---

## 10. 第 9 章：加入 prompt.py 和项目规则

### 本章目标

让 Agent 知道当前工作目录、日期、平台、shell、项目规则。

### 本章新增文件

```text
mini_claude_rebuild/
  prompt.py
```

### 本章最小实现

```python
from pathlib import Path
from datetime import date
import platform


def build_system_prompt() -> str:
    return f"""You are Mini Claude Code.
Working directory: {Path.cwd()}
Date: {date.today().isoformat()}
Platform: {platform.system()}
"""
```

### 本章逐步扩展

1. 加载 `CLAUDE.md`。
2. 支持 `@./path` include。
3. 加载 `.claude/rules/*.md`。
4. 加入 git branch、recent commits、status。

### 验收命令

写入规则：

```text
When the user greets you, respond in Chinese.
```

运行：

```bash
mini-claude-rebuild "hello"
```

预期：模型按规则中文回应。

### 过渡到源码

最终 `prompt.py` 会继续注入 memory、skills、agents、deferred tools。

---

## 11. 第 10 章：从 one-shot 过渡到 REPL

### 本章目标

支持交互式使用：用户可以一直输入，Agent 保持上下文。

### 本章扩展 `__main__.py`

新增：

```python
async def run_repl(agent: Agent) -> None:
    while True:
        line = input("> ").strip()
        if line in ("exit", "quit"):
            break
        if line == "/clear":
            agent.clear_history()
            continue
        await agent.chat(line)
```

### 本章需要给 `Agent` 增加

```python
def clear_history(self) -> None:
    self.messages.clear()
```

### 验收命令

```bash
mini-claude-rebuild
> hello
> /clear
> exit
```

### 过渡到源码

最终 REPL 会支持 `/plan`、`/cost`、`/compact`、`/memory`、`/skills`、`/<skill>`。

---

## 12. 第 11 章：加入 session.py，实现 --resume

### 本章目标

退出后还能恢复上一轮对话。

### 本章新增文件

```text
mini_claude_rebuild/
  session.py
```

### 本章实现函数

```python
def save_session(session_id: str, data: dict) -> None: ...
def load_session(session_id: str) -> dict | None: ...
def list_sessions() -> list[dict]: ...
def get_latest_session_id() -> str | None: ...
```

### 本章 Agent 增量

1. `Agent.__init__()` 生成 `session_id`。
2. 每次 `chat()` 结束自动保存 messages。
3. 增加 `restore_session(data)`。

### 验收命令

```bash
mini-claude-rebuild "My temporary project code word is blue build."
mini-claude-rebuild --resume "What is my temporary project code word?"
```

---

## 13. 第 12 章：加入权限模式

### 本章目标

开始向真实 Coding Agent 靠近：不是所有工具都能无条件执行。

### 本章新增概念

```text
default
plan
acceptEdits
bypassPermissions
dontAsk
```

### 本章扩展点

| 文件 | 改什么 |
|------|--------|
| `__main__.py` | 增加 `--yolo`、`--plan`、`--accept-edits`、`--dont-ask` |
| `tools.py` | 增加 `check_permission()` |
| `agent.py` | 执行工具前先检查权限 |

### 本章先实现简单版

| 工具类型 | 默认模式 |
|----------|----------|
| read/list/grep | 自动允许 |
| write/edit | 需要确认 |
| shell | 需要确认 |

### 验收命令

```bash
mini-claude-rebuild "Create a file named permission_test.txt."
mini-claude-rebuild --yolo "Create a file named permission_test.txt."
mini-claude-rebuild --dont-ask "Create a file named permission_test.txt."
```

### 过渡到源码

最终版本要继续加入 allow/deny settings、危险命令检测、读前编辑、mtime 保护。

---

## 14. 第 13 章：实现流式输出

### 本章目标

把“等模型完整返回再显示”改为“边生成边显示”。

### 本章改动

| 文件 | 改什么 |
|------|--------|
| `agent.py` | 新增 `_call_openai_stream()` |
| `ui.py` | 支持连续文本输出 |

### 本章步骤

1. 把 `messages.create()` 换成 `messages.stream()`。
2. 处理 text delta。
3. 拼接 tool_use 的 name、id、input。
4. 流结束后返回完整 response 结构。

### 验收命令

```bash
mini-claude-rebuild "Write a short explanation of Agent Loop."
```

预期：文本逐步出现，不是一次性出现。

---

## 15. 第 14 章：补 Anthropic 后端，形成双后端

### 本章目标

前面章节已经用 DeepSeek 的 OpenAI 兼容格式跑通模型调用。本章再补 Anthropic 原生格式，让项目逐步接近当前源码里的双后端结构。

### 本章改动

| 文件 | 改什么 |
|------|--------|
| `agent.py` | 增加 `_chat_anthropic()`，并保留已有 OpenAI 兼容路径 |
| `__main__.py` | 解析 `ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`，并按环境变量选择后端 |

### 本章关键转换

```text
OpenAI-compatible messages
  -> Anthropic messages

OpenAI-compatible tool calls
  -> Anthropic tool_use / tool_result
```

### 验收命令

```bash
DEEPSEEK_API_KEY=sk-xxx mini-claude-rebuild --model deepseek-v4-flash "hello"
ANTHROPIC_API_KEY=sk-ant-xxx mini-claude-rebuild --model claude-opus-4-6 "hello"
```

---

## 16. 第 15 章：加入上下文压缩

### 本章目标

处理长对话、大文件和大量工具结果。

### 本章建议分三步写

| 步 | 功能 |
|----|------|
| 1 | 工具结果超过阈值就截断 |
| 2 | 大结果保存到磁盘，只把预览放入上下文 |
| 3 | 手动 `/compact` 调模型总结历史 |

### 本章改动

| 文件 | 改什么 |
|------|--------|
| `agent.py` | `_persist_large_result()`、`compact()`、`_run_compression_pipeline()` |
| `__main__.py` | 增加 `/compact` |

### 验收命令

```bash
mini-claude-rebuild --yolo "Read test/large-file.txt and summarize it."
```

---

## 17. 第 16 章：实现 frontmatter.py

### 本章目标

为 memory、skills、subagent 配置打基础。

### 本章新增文件

```text
mini_claude_rebuild/
  frontmatter.py
```

### 本章实现

```python
class FrontmatterResult:
    meta: dict[str, str]
    body: str


def parse_frontmatter(content: str) -> FrontmatterResult: ...
def format_frontmatter(meta: dict[str, str], body: str) -> str: ...
```

### 验收

输入：

```markdown
---
name: commit
description: Create a commit
---
Body text
```

能解析出 `name`、`description` 和正文。

---

## 18. 第 17 章：实现 memory.py

### 本章目标

让 Agent 具备长期记忆。

### 本章新增文件

```text
mini_claude_rebuild/
  memory.py
```

### 本章分阶段写

| 小节 | 功能 |
|------|------|
| 17.1 | `get_memory_dir()` |
| 17.2 | `save_memory()` |
| 17.3 | `list_memories()` |
| 17.4 | `MEMORY.md` 索引 |
| 17.5 | `scan_memory_headers()` |
| 17.6 | `select_relevant_memories()` |
| 17.7 | 注入 system prompt |

### 验收命令

```bash
mini-claude-rebuild --yolo "Save a project memory saying this repo teaches coding agents."
mini-claude-rebuild --yolo "What does this repo teach?"
```

---

## 19. 第 18 章：实现 skills.py

### 本章目标

让项目可以加载 `.claude/skills/<name>/SKILL.md`。

### 本章新增文件

```text
mini_claude_rebuild/
  skills.py
```

### 本章分阶段写

1. 扫描用户级 `~/.claude/skills`。
2. 扫描项目级 `.claude/skills`。
3. 解析 `SKILL.md` frontmatter。
4. 支持 `$ARGUMENTS` 替换。
5. 支持 `${CLAUDE_SKILL_DIR}` 替换。
6. 在 prompt 中列出技能。
7. 在 REPL 中支持 `/<skill>`。

### 验收命令

```bash
mini-claude-rebuild
> /skills
```

---

## 20. 第 19 章：实现 Plan Mode

### 本章目标

实现“只读分析 -> 写计划 -> 用户审批 -> 执行”的工作流。

### 本章改动

| 文件 | 改什么 |
|------|--------|
| `tools.py` | 加 `enter_plan_mode`、`exit_plan_mode` 工具 |
| `agent.py` | 加 plan 状态和 plan 文件 |
| `ui.py` | 展示 plan 和审批选项 |
| `__main__.py` | 增加 `/plan` 和 `--plan` |

### 验收命令

```bash
mini-claude-rebuild --plan "Plan how to add a new tool."
```

---

## 21. 第 20 章：实现 subagent.py

### 本章目标

让主 Agent 能启动子 Agent，并把结果带回来。

### 本章新增文件

```text
mini_claude_rebuild/
  subagent.py
```

### 本章功能

1. 内置 `explore`、`plan`、`general` 三种 Agent。
2. 从 `.claude/agents` 加载自定义 Agent。
3. `agent` 工具创建新的 `Agent` 实例。
4. 子 Agent 使用独立上下文。
5. 子 Agent 结果返回主 Agent。

### 验收命令

```bash
mini-claude-rebuild --yolo "Use an explore agent to inspect python/mini_claude and summarize the files."
```

---

## 22. 第 21 章：实现 MCP 客户端

### 本章目标

接入外部工具服务器。

### 本章新增文件

```text
mini_claude_rebuild/
  mcp_client.py
```

### 本章分阶段写

| 小节 | 功能 |
|------|------|
| 21.1 | `McpConnection.connect()` 启动进程 |
| 21.2 | JSON-RPC request/response |
| 21.3 | `initialize` |
| 21.4 | `tools/list` |
| 21.5 | `tools/call` |
| 21.6 | `McpManager` 管理多个 server |
| 21.7 | 工具名加 `mcp__server__tool` 前缀 |

### 验收命令

```bash
mini-claude-rebuild --yolo "Use the MCP add tool to calculate 17+25."
```

---

## 23. 第 22 章：最终对齐当前源码

### 本章目标

把教学版逐步补齐成当前源码的完整形态。

### 对齐清单

| 源码模块 | 教学版最终必须拥有 |
|----------|--------------------|
| `__main__.py` | 参数解析、one-shot、REPL、resume、skills、plan approval |
| `agent.py` | Agent Loop、双后端、流式、权限、压缩、MCP、sub-agent、预算控制 |
| `tools.py` | 读写改列搜 shell web skill plan agent tool_search |
| `ui.py` | Rich 输出、工具摘要、错误、重试、费用、plan、sub-agent |
| `prompt.py` | 系统提示词、include、rules、git、memory、skills、agents |
| `session.py` | 保存、读取、列出、最近会话 |
| `frontmatter.py` | metadata 解析和格式化 |
| `memory.py` | 4 类记忆、索引、语义选择、注入 |
| `skills.py` | 技能发现、解析、参数替换、prompt 描述 |
| `subagent.py` | 内置 Agent、自定义 Agent、描述注入 |
| `mcp_client.py` | stdio JSON-RPC、工具发现、工具转发 |

### 最终验收顺序

```bash
mini-claude-rebuild --help
mini-claude-rebuild "hello"
mini-claude-rebuild --yolo "Read python/mini_claude/agent.py and summarize it."
mini-claude-rebuild --yolo "Search for build_system_prompt."
mini-claude-rebuild --plan "Plan a small refactor."
mini-claude-rebuild --resume
```

---

## 24. 推荐实际写代码方式

每章都按这个节奏推进：

1. 先写最小可运行代码。
2. 运行本章验收命令。
3. 只修本章暴露的问题。
4. 提交或保存一个章节快照。
5. 再进入下一章。

建议快照命名：

```text
chapter-01-cli
chapter-02-chat
chapter-03-read-file-tool
chapter-04-agent-loop
chapter-05-file-discovery
...
chapter-22-final-align
```

这样学习时能清楚看到代码如何从几十行，逐步增长到当前项目的完整实现。
