from __future__ import annotations

from typing import Any

from mini_claude_code.app.bootstrap import (
    build_app_context,
    build_main_registry,
    build_tool_runner,
    load_app_config,
    persist_env_var,
)
from mini_claude_code.app.context import AppContext
from mini_claude_code.domain.state import LoopState, generate_session_id
from mini_claude_code.runtime.loop import agent_loop
from mini_claude_code.runtime.permission import MODES, _select_option


# 修复 input 获取输入的 bug，只需要导入 readline 模块
# 获取输入依旧使用 input
try:
    import readline

    # #143 UTF-8 backspace fix for macOS libedit
    readline.parse_and_bind("set bind-tty-special-chars off")
    readline.parse_and_bind("set input-meta on")
    readline.parse_and_bind("set output-meta on")
    readline.parse_and_bind("set convert-meta off")
    readline.parse_and_bind("set enable-meta-keybindings on")
except ImportError:
    pass


def _print_startup_banner() -> None:
    cat = r"""
 /\_/\__
( o.o  )\_
 > ^ <   _)
   \  \  \
   (__/  /
     /__/
"""
    print(cat.rstrip("\n"))
    print("Welcome to Welkin's agent")
    print("Let's build something amazing")
    print()


def _ask_mode() -> str:
    print("Select permission mode:")
    return _select_option("Mode:", list(MODES), default_idx=0)


def _persist_mode(mode: str) -> None:
    if persist_env_var("AGENT_MODE", mode):
        print(f"  [.env] AGENT_MODE={mode}")
    else:
        print("  [.env] .env not found, mode not persisted")


def _on_tool_use(tool_name: str, tool_input: dict[str, Any]) -> None:
    if tool_name == "bash" and isinstance(tool_input.get("command"), str):
        print(f"\033[33m$ {tool_input['command']}\033[0m")


def _print_assistant_text(messages: list[dict[str, Any]]) -> None:
    """把最后一条消息里的纯文本块打印出来。"""
    if not messages:
        return
    last = messages[-1].get("content")
    if isinstance(last, list):
        for block in last:
            if hasattr(block, "text"):
                print(block.text)
    print()


def run_repl(ctx: AppContext) -> None:
    """命令行 REPL：读取用户输入，反复调用 ``agent_loop``，直到用户退出。"""
    registry = build_main_registry(ctx)
    tool_runner = build_tool_runner(ctx, registry, on_tool_use=_on_tool_use)

    history: list[dict[str, Any]] = []
    state = LoopState(
        messages=history
    )  # 状态，包含历史消息、会话 ID、轮次、对话状态转移原因

    for cb in ctx.on_startup:
        cb(ctx)

    try:
        while True:
            try:
                query = input("\033[36mwa >> \033[0m")
            except (EOFError, KeyboardInterrupt):
                break

            stripped = query.strip().lower()
            if stripped in ("q", "quit", "exit", ""):
                break

            if stripped == "/mode":
                current = ctx.permission.mode
                print(f"  Current mode: \033[1m{current}\033[0m")
                new_mode = _select_option(
                    "Select mode:", list(MODES), default_idx=MODES.index(current)
                )
                ctx.permission.set_mode(new_mode)
                _persist_mode(new_mode)
                print(f"  Mode switched to \033[1m{new_mode}\033[0m")
                continue

            # 每次新用户输入即是一个新任务，分配新的 session_id
            # agent_loop 内部每次 LLM 调用后会把 session_id 交给 usage，
            # 下一次用户输入生成新 id 时，计算器自动打印上一个任务的合计并重置
            state.session_id = generate_session_id()
            history.append({"role": "user", "content": query})

            agent_loop(
                state=state,
                client=ctx.client,
                tools=registry.tool_specs(),
                tool_runner=tool_runner,
                config=ctx.main_loop_config,
                workspace=ctx.workspace,
                compact_state=ctx.compact_state,
                llm_logger=ctx.llm_logger,
                usage=ctx.usage,
                hooks=ctx.hooks,
                loop_hooks=ctx.loop_hooks,
            )

            _print_assistant_text(history)
    finally:
        ctx.usage.flush()
        for cb in ctx.on_shutdown:
            cb(ctx)


def main() -> None:
    _print_startup_banner()
    config = load_app_config()
    if config.agent_mode in MODES:
        mode = config.agent_mode
        print(f"Mode: \033[1m{mode}\033[0m (from .env)")
        print()
    else:
        mode = _ask_mode()
    ctx = build_app_context(mode=mode, config=config)
    run_repl(ctx)
