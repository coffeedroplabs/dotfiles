# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=1.2.0,<2",
#     "openai>=1.40.0",
# ]
# ///
"""
DeepSeek executor MCP server: Claude Code orchestrates, DeepSeek writes files on disk.
When to delegate is decided by the /deepseek-run command, not here.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from openai import APIError, AsyncOpenAI
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionMessage

# The stdio transport owns stdout; anything logged there corrupts the JSON-RPC stream.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

mcp = FastMCP("deepseek-executor")

ENV_FILE = Path.home() / ".config" / "claude-mcp" / "deepseek-executor" / ".env"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

SEARCH, DIVIDER, REPLACE = "<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"

IMPLEMENT_SYSTEM = (
    "You are an expert software engineer executing a spec from a principal architect. "
    "Write clean, production-ready, idiomatic code with no placeholders. "
    "Deliver the complete file by calling write_file exactly once."
)

# The file arrives as a tool argument rather than as reply text: asked for raw file text,
# deepseek-flash sometimes appends a stray "</parameter>" from its tool-call template
# (about 1 reply in 12) or wraps the file in fences. DeepSeek's own parser strips the
# real template delimiters from tool arguments. Thinking mode rejects a forced tool_choice,
# so the system prompt asks for the call instead.
WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Save the complete content of the target file.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The entire file content, exactly as it should be saved.",
                }
            },
            "required": ["content"],
        },
    },
}

PATCH_SYSTEM = (
    "You are an expert software engineer making precise edits to an existing file.\n"
    "Reply with one or more blocks in exactly this format:\n\n"
    f"{SEARCH}\n"
    "whole lines copied exactly from the current file\n"
    f"{DIVIDER}\n"
    "replacement lines\n"
    f"{REPLACE}\n\n"
    "Rules:\n"
    "1. SEARCH holds whole lines that match the file character-for-character, including indentation.\n"
    "2. Each SEARCH must match exactly one place in the file; add surrounding lines until it is unique.\n"
    "3. To delete lines, leave the replacement section empty.\n"
    "4. Blocks are applied in order, each against the result of the previous one.\n"
    "5. Reply with blocks only, no commentary."
)


class ExecutorError(Exception):
    """A failure reported back to Claude as the tool result."""


def load_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def get_client() -> AsyncOpenAI:
    api_key = load_api_key()
    if not api_key:
        raise ExecutorError(
            f"DEEPSEEK_API_KEY is not set. Export it or put DEEPSEEK_API_KEY=... in {ENV_FILE}."
        )
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    # Thinking mode can take minutes on a large file. Retries are left to the
    # orchestrator so a timed-out request is never silently re-run and re-billed.
    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=600.0, max_retries=0)


def resolve_target(file_path: str) -> Path:
    target = Path(file_path)
    if not target.is_absolute():
        # The server's cwd is wherever Claude Code was launched, not the directory
        # Claude is working in (e.g. a worktree), so a relative path is ambiguous.
        raise ExecutorError(f"file_path must be absolute, got '{file_path}'.")
    target = target.resolve()
    # The orchestrator reviews and reverts these writes with git, and they bypass
    # Claude Code's checkpoints, so refuse paths git cannot see.
    if not any((parent / ".git").exists() for parent in target.parents):
        raise ExecutorError(f"'{target}' is not inside a git work tree.")
    return target


def read_file(path: Path) -> str:
    try:
        # newline="" keeps CRLF intact instead of silently converting it to LF.
        with path.open(encoding="utf-8", newline="") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise ExecutorError(f"Cannot read '{path}': {e}") from e


def write_file(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            f.write(content)
    except OSError as e:
        raise ExecutorError(f"Cannot write '{path}': {e}") from e


def read_context(context_files: list[str]) -> str:
    bad = [
        p for p in context_files if not (Path(p).is_absolute() and Path(p).is_file())
    ]
    if bad:
        raise ExecutorError(
            "context_files must be absolute paths to existing files: " + ", ".join(bad)
        )
    return "".join(
        f'<file path="{p}">\n{read_file(Path(p))}\n</file>\n\n' for p in context_files
    )


def split_lines(text: str) -> list[str]:
    """Split on \\n only, keeping endings; str.splitlines also breaks on \\f, \\u2028 and others."""
    return re.findall(r"[^\n]*\n|[^\n]+\Z", text)


def bare(line: str) -> str:
    return line.removesuffix("\n").removesuffix("\r")


def format_usage(usage: CompletionUsage | None) -> str:
    if usage is None:
        return "Usage: unavailable."
    hit = getattr(usage, "prompt_cache_hit_tokens", None) or 0
    miss = getattr(usage, "prompt_cache_miss_tokens", None) or 0
    reasoning = getattr(usage.completion_tokens_details, "reasoning_tokens", None) or 0
    return (
        f"Usage: prompt {usage.prompt_tokens} (cache hit {hit}, miss {miss}), "
        f"completion {usage.completion_tokens} (reasoning {reasoning})."
    )


async def complete(
    model: str, system: str, user: str, **request
) -> tuple[ChatCompletionMessage, str]:
    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **request,
        )
    except APIError as e:
        raise ExecutorError(f"DeepSeek API error: {e}") from e
    choice = response.choices[0]
    if choice.finish_reason not in ("stop", "tool_calls"):
        raise ExecutorError(
            f"DeepSeek stopped with finish_reason='{choice.finish_reason}'; nothing was written. "
            f"{format_usage(response.usage)}"
        )
    return choice.message, format_usage(response.usage)


def build_prompt(
    context: str, target: Path, current: str | None, instruction: str
) -> str:
    # Stable parts first: DeepSeek's context cache only hits on an exact prefix,
    # so calls in one session that share context files reuse it.
    prompt = context
    if current is not None:
        prompt += f'<current_file path="{target}">\n{current}\n</current_file>\n\n'
    else:
        prompt += f"Target file (new): {target}\n\n"
    return prompt + f"Instructions:\n{instruction}\n"


def file_content(message: ChatCompletionMessage) -> str:
    calls = [c for c in message.tool_calls or [] if c.function.name == "write_file"]
    if len(calls) != 1:
        raise ExecutorError(
            f"DeepSeek made {len(calls)} write_file calls (needs exactly 1); nothing was "
            f"written. Reply text: {(message.content or '')[:400]!r}"
        )
    try:
        content = json.loads(calls[0].function.arguments)["content"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ExecutorError(
            f"Malformed write_file arguments ({e!r}); nothing was written."
        ) from e
    if not isinstance(content, str):
        raise ExecutorError("write_file content is not a string; nothing was written.")
    return content


def parse_blocks(reply: str) -> list[tuple[list[str], list[str]]]:
    blocks: list[tuple[list[str], list[str]]] = []
    search: list[str] = []
    replace: list[str] = []
    state = None
    for raw in split_lines(reply):
        line = bare(raw)
        marker = line.rstrip()
        if state is None:
            if marker == SEARCH:
                state, search, replace = "search", [], []
            elif marker in (DIVIDER, REPLACE):
                raise ExecutorError(f"Malformed reply: '{marker}' outside a block.")
            # Anything else between blocks (prose, fences) carries no edit.
        elif state == "search":
            if marker == DIVIDER:
                if not search:
                    raise ExecutorError("Malformed reply: empty SEARCH section.")
                state = "replace"
            elif marker in (SEARCH, REPLACE):
                raise ExecutorError(
                    f"Malformed reply: '{marker}' inside a SEARCH section."
                )
            else:
                search.append(line)
        else:
            if marker == REPLACE:
                blocks.append((search, replace))
                state = None
            elif marker in (SEARCH, DIVIDER):
                raise ExecutorError(
                    f"Malformed reply: '{marker}' inside a replacement section. If the file "
                    "itself contains marker lines, edit it with implement_file_with_deepseek."
                )
            else:
                replace.append(line)
    if state is not None:
        raise ExecutorError("Malformed reply: unterminated block.")
    if not blocks:
        raise ExecutorError(
            f"DeepSeek returned no SEARCH/REPLACE blocks:\n{reply[:400]}"
        )
    return blocks


def apply_blocks(content: str, blocks: list[tuple[list[str], list[str]]]) -> str:
    newline = "\r\n" if "\r\n" in content else "\n"
    lines = split_lines(content)
    for idx, (search, replace) in enumerate(blocks, 1):
        bare_lines = [bare(line) for line in lines]
        n = len(search)
        starts = [
            i for i in range(len(lines) - n + 1) if bare_lines[i : i + n] == search
        ]
        if len(starts) != 1:
            snippet = "\n".join(search)
            raise ExecutorError(
                f"SEARCH block #{idx} matched {len(starts)} times (needs exactly 1); "
                f"nothing was written.\n```\n{snippet}\n```"
            )
        i = starts[0]
        last = lines[i + n - 1]
        new = [line + newline for line in replace]
        if new:
            # Keep the original ending of the last replaced line, which may be none at EOF.
            new[-1] = replace[-1] + last[len(bare(last)) :]
        lines[i : i + n] = new
    return "".join(lines)


@mcp.tool()
async def implement_file_with_deepseek(
    file_path: str,
    instruction: str,
    context_files: list[str] | None = None,
    model: str = "",
) -> str:
    """
    Create a file, or replace an existing file entirely, with content written by DeepSeek.

    Args:
        file_path: Absolute path inside a git work tree.
        instruction: Full spec for the file: behavior, interfaces, constraints.
        context_files: Absolute paths of files DeepSeek should see (types, sister modules,
            tests). Keep the order stable across calls so DeepSeek's prompt cache hits.
        model: Model override; defaults to $DEEPSEEK_MODEL or deepseek-flash.
    """
    selected_model = model or DEFAULT_MODEL
    try:
        target = resolve_target(file_path)
        context = read_context(context_files or [])
        current = read_file(target) if target.exists() else None
        message, usage = await complete(
            selected_model,
            IMPLEMENT_SYSTEM,
            build_prompt(context, target, current, instruction),
            tools=[WRITE_FILE_TOOL],
        )
        content = file_content(message).strip("\n")
        if not content:
            raise ExecutorError("DeepSeek returned empty content; nothing was written.")
        content += "\n"
        if current is not None and "\r\n" in current:
            content = content.replace("\r\n", "\n").replace("\n", "\r\n")
        write_file(target, content)
    except ExecutorError as e:
        return f"Error: {e}"
    return f"Wrote {target} ({len(split_lines(content))} lines) with {selected_model}. {usage}"


@mcp.tool()
async def patch_file_with_deepseek(
    file_path: str,
    instruction: str,
    context_files: list[str] | None = None,
    model: str = "",
) -> str:
    """
    Edit an existing file with SEARCH/REPLACE blocks written by DeepSeek.
    All blocks apply or none do; each SEARCH must match exactly one run of whole lines.

    Args:
        file_path: Absolute path of an existing file inside a git work tree.
        instruction: What to change and why.
        context_files: Absolute paths of files DeepSeek should see (types, callers, tests).
            Keep the order stable across calls so DeepSeek's prompt cache hits.
        model: Model override; defaults to $DEEPSEEK_MODEL or deepseek-flash.
    """
    selected_model = model or DEFAULT_MODEL
    try:
        target = resolve_target(file_path)
        if not target.is_file():
            raise ExecutorError(
                f"'{target}' does not exist; use implement_file_with_deepseek to create it."
            )
        context = read_context(context_files or [])
        current = read_file(target)
        message, usage = await complete(
            selected_model,
            PATCH_SYSTEM,
            build_prompt(context, target, current, instruction),
        )
        blocks = parse_blocks(message.content or "")
        patched = apply_blocks(current, blocks)
        write_file(target, patched)
    except ExecutorError as e:
        return f"Error: {e}"
    return (
        f"Patched {target}: {len(blocks)} block(s), now {len(split_lines(patched))} lines, "
        f"with {selected_model}. {usage}"
    )


if __name__ == "__main__":
    mcp.run()
