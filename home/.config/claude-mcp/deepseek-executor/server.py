# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=2.3,<3",
#     "openai>=1.40.0",
# ]
# ///
"""
DeepSeek executor MCP server: Claude Code orchestrates, DeepSeek writes files on disk.
When to delegate is decided by the /deepseek-run skill, not here.
"""

import asyncio
import difflib
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from openai import APIError, AsyncOpenAI, Timeout
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletionChunk

# The stdio transport owns stdout; anything logged there corrupts the JSON-RPC stream.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("deepseek-executor")

mcp = MCPServer("deepseek-executor")

ENV_FILE = Path.home() / ".config" / "claude-mcp" / "deepseek-executor" / ".env"
LOG_FILE = (
    Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    / "deepseek-executor"
    / "calls.jsonl"
)
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

CONTEXT_TOKENS = 1_048_576
MAX_OUTPUT_TOKENS = 393_216
PROGRESS_INTERVAL = 2.0
DIFF_LINE_LIMIT = 400

Effort = Literal["none", "low", "high", "max"]

# Overwrites files in place and calls a paid external API; a repeat call yields different code.
WRITES_FILE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
)

# Each call holds its file's lock from reading it until writing it, so two backgrounded
# calls on one file run one after the other instead of the second clobbering the first.
FILE_LOCKS: defaultdict[Path, asyncio.Lock] = defaultdict(asyncio.Lock)

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
# so the call is forced only with thinking off; the system prompt asks for it either way.
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
FORCE_WRITE_FILE = {"type": "function", "function": {"name": "write_file"}}

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
        raise ToolError(
            f"DEEPSEEK_API_KEY is not set. Export it or put DEEPSEEK_API_KEY=... in {ENV_FILE}."
        )
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    # Replies are streamed, so the errors the SDK retries (429, 5xx, connection) arrive before
    # any token and a retry never re-bills a finished generation. With streaming the read
    # timeout applies between chunks, not to the whole multi-minute reply.
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=Timeout(600.0, connect=10.0),
        max_retries=2,
    )


def max_tokens_for(prompt: str) -> int:
    # Unset, DeepSeek caps output at 8K tokens without thinking, which truncates large files.
    # It rejects prompt + max_tokens beyond the context window (a free 400), so leave room
    # for the prompt, estimated at about 3 characters per token for code.
    return min(MAX_OUTPUT_TOKENS, max(CONTEXT_TOKENS - len(prompt) // 3, 8192))


def resolve_target(file_path: str) -> Path:
    target = Path(file_path)
    if not target.is_absolute():
        # The server's cwd is wherever Claude Code was launched, not the directory
        # Claude is working in (e.g. a worktree), so a relative path is ambiguous.
        raise ToolError(f"file_path must be absolute, got '{file_path}'.")
    target = target.resolve()
    # The orchestrator reviews and reverts these writes with git, and they bypass
    # Claude Code's checkpoints, so refuse paths git cannot see.
    if not any((parent / ".git").exists() for parent in target.parents):
        raise ToolError(f"'{target}' is not inside a git work tree.")
    return target


def read_file(path: Path) -> str:
    try:
        # newline="" keeps CRLF intact instead of silently converting it to LF.
        with path.open(encoding="utf-8", newline="") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise ToolError(f"Cannot read '{path}': {e}") from e


def read_current(path: Path) -> str | None:
    return read_file(path) if path.exists() else None


def current_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def write_file(path: Path, content: str) -> None:
    # A sibling temp file renamed over the target means a crash or cancel never leaves a
    # half-written file. mkstemp creates it as 0600, so carry over the target's mode.
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = (
            path.stat().st_mode & 0o7777 if path.exists() else 0o666 & ~current_umask()
        )
        fd, tmp = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError as e:
        raise ToolError(f"Cannot write '{path}': {e}") from e


def undo_command(target: Path, before: str | None) -> str:
    """Save the pre-image as a git object, since /rewind does not cover these writes."""
    quoted = shlex.quote(str(target))
    if before is None:
        return f"Undo: rm {quoted}"
    try:
        result = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            input=before.encode("utf-8"),
            cwd=target.parent,
            capture_output=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        stderr = (getattr(e, "stderr", None) or b"").decode(errors="replace").strip()
        raise ToolError(
            f"Cannot save the current '{target}' to git for undo ({stderr or e}); "
            "nothing was written."
        ) from e
    sha = result.stdout.decode().strip()
    parent = shlex.quote(str(target.parent))
    return f"Undo: git -C {parent} cat-file blob {sha} > {quoted}"


def describe_change(target: Path, before: str | None, after: str) -> str:
    diff = list(
        difflib.unified_diff(
            [bare(line) for line in split_lines(before or "")],
            [bare(line) for line in split_lines(after)],
            "/dev/null" if before is None else str(target),
            str(target),
            lineterm="",
        )
    )
    added = sum(line.startswith("+") for line in diff[2:])
    removed = sum(line.startswith("-") for line in diff[2:])
    stats = f"Changes: +{added} -{removed} lines"
    if len(diff) > DIFF_LINE_LIMIT:
        return f"{stats}; the diff is too long to show, so review the file itself."
    return f"{stats}.\n```diff\n" + "\n".join(diff) + "\n```"


def save(target: Path, before: str | None, after: str) -> str:
    """Write after over before and return the undo command and the diff."""
    if read_current(target) != before:
        # Claude or the user edited the file while the call ran in the background.
        raise ToolError(
            f"'{target}' changed while DeepSeek was generating; nothing was written. "
            "Re-run against the current file."
        )
    if after == before:
        raise ToolError(
            "DeepSeek's result is identical to the current file; nothing was written."
        )
    undo = undo_command(target, before)
    write_file(target, after)
    return f"{undo}\n{describe_change(target, before, after)}"


def read_context(context_files: list[str]) -> str:
    bad = [
        p for p in context_files if not (Path(p).is_absolute() and Path(p).is_file())
    ]
    if bad:
        raise ToolError(
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


def usage_numbers(usage: CompletionUsage | None) -> dict[str, int]:
    if usage is None:
        return {}
    return {
        "prompt_tokens": usage.prompt_tokens,
        "cache_hit_tokens": getattr(usage, "prompt_cache_hit_tokens", None) or 0,
        "cache_miss_tokens": getattr(usage, "prompt_cache_miss_tokens", None) or 0,
        "completion_tokens": usage.completion_tokens,
        "reasoning_tokens": getattr(
            usage.completion_tokens_details, "reasoning_tokens", None
        )
        or 0,
    }


def format_usage(usage: CompletionUsage | None) -> str:
    n = usage_numbers(usage)
    if not n:
        return "Usage: unavailable."
    return (
        f"Usage: prompt {n['prompt_tokens']} (cache hit {n['cache_hit_tokens']}, "
        f"miss {n['cache_miss_tokens']}), completion {n['completion_tokens']} "
        f"(reasoning {n['reasoning_tokens']})."
    )


def log_call(record: dict) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as e:
        log.warning("Cannot append to %s: %s", LOG_FILE, e)


@dataclass
class Reply:
    """A streamed chat completion, accumulated chunk by chunk."""

    content: str = ""
    tool_calls: dict[int, dict[str, str]] = field(default_factory=dict)
    reasoning_chars: int = 0
    finish_reason: str | None = None
    usage: CompletionUsage | None = None

    def add(self, chunk: ChatCompletionChunk) -> None:
        if chunk.usage:
            self.usage = chunk.usage
        for choice in chunk.choices:
            delta = choice.delta
            self.content += delta.content or ""
            # DeepSeek's thinking text is an extension field outside the OpenAI schema.
            self.reasoning_chars += len(getattr(delta, "reasoning_content", None) or "")
            for tool_call in delta.tool_calls or []:
                call = self.tool_calls.setdefault(
                    tool_call.index, {"name": "", "arguments": ""}
                )
                if tool_call.function:
                    call["name"] += tool_call.function.name or ""
                    call["arguments"] += tool_call.function.arguments or ""
            if choice.finish_reason:
                self.finish_reason = choice.finish_reason

    @property
    def generated_chars(self) -> int:
        arguments = sum(len(c["arguments"]) for c in self.tool_calls.values())
        return len(self.content) + arguments + self.reasoning_chars

    def status(self) -> str:
        status = f"DeepSeek generated {self.generated_chars / 1000:.1f}k chars"
        if self.reasoning_chars:
            status += f" ({self.reasoning_chars / 1000:.1f}k thinking)"
        return status


class Call:
    """One tool invocation: streams from DeepSeek, reports progress, logs one JSONL line."""

    def __init__(
        self, ctx: Context, tool: str, file_path: str, model: str, effort: Effort
    ):
        self.ctx, self.model, self.effort = ctx, model, effort
        self.started = time.monotonic()
        self.record: dict = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "tool": tool,
            "file": file_path,
            "model": model,
            "effort": effort,
        }

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.record["duration_s"] = round(time.monotonic() - self.started, 1)
        if exc is None:
            self.record["outcome"] = "ok"
        elif isinstance(exc, asyncio.CancelledError):
            self.record["outcome"] = "cancelled"
        else:
            self.record["outcome"] = "error"
            self.record["error"] = f"{type(exc).__name__}: {exc}"[:500]
        log_call(self.record)
        if exc is not None and not isinstance(exc, (ToolError, asyncio.CancelledError)):
            # The SDK reports any other exception as a bare "Error executing tool",
            # which leaves Claude nothing to act on.
            raise ToolError(f"Unexpected {type(exc).__name__}: {exc}") from exc

    def summary(self) -> str:
        elapsed = time.monotonic() - self.started
        return f"{self.model} (reasoning {self.effort}) in {elapsed:.1f}s"

    async def complete(self, system: str, user: str, **request) -> Reply:
        client = get_client()
        reply = Reply()
        last_report = time.monotonic()
        try:
            # Leaving the stream on cancel closes the connection, so DeepSeek stops
            # generating (and billing) and nothing is written.
            async with await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                reasoning_effort=self.effort,
                max_tokens=max_tokens_for(system + user),
                stream=True,
                stream_options={"include_usage": True},
                **request,
            ) as stream:
                async for chunk in stream:
                    reply.add(chunk)
                    # Progress resets Claude Code's MCP idle timeout and shows liveness
                    # for calls it has moved to the background.
                    if time.monotonic() - last_report >= PROGRESS_INTERVAL:
                        last_report = time.monotonic()
                        await self.ctx.report_progress(
                            reply.generated_chars, None, reply.status()
                        )
        except APIError as e:
            raise ToolError(f"DeepSeek API error: {e}") from e
        finally:
            self.record.update(
                finish_reason=reply.finish_reason, **usage_numbers(reply.usage)
            )
        if reply.finish_reason not in ("stop", "tool_calls"):
            raise ToolError(
                f"DeepSeek stopped with finish_reason='{reply.finish_reason}'; nothing was "
                f"written. {format_usage(reply.usage)}"
            )
        return reply


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


def file_content(reply: Reply) -> str:
    calls = [c for c in reply.tool_calls.values() if c["name"] == "write_file"]
    if len(calls) != 1:
        raise ToolError(
            f"DeepSeek made {len(calls)} write_file calls (needs exactly 1); nothing was "
            f"written. Reply text: {reply.content[:400]!r}"
        )
    try:
        content = json.loads(calls[0]["arguments"])["content"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ToolError(
            f"Malformed write_file arguments ({e!r}); nothing was written."
        ) from e
    if not isinstance(content, str):
        raise ToolError("write_file content is not a string; nothing was written.")
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
                raise ToolError(f"Malformed reply: '{marker}' outside a block.")
            # Anything else between blocks (prose, fences) carries no edit.
        elif state == "search":
            if marker == DIVIDER:
                if not search:
                    raise ToolError("Malformed reply: empty SEARCH section.")
                state = "replace"
            elif marker in (SEARCH, REPLACE):
                raise ToolError(f"Malformed reply: '{marker}' inside a SEARCH section.")
            else:
                search.append(line)
        else:
            if marker == REPLACE:
                blocks.append((search, replace))
                state = None
            elif marker in (SEARCH, DIVIDER):
                raise ToolError(
                    f"Malformed reply: '{marker}' inside a replacement section. If the file "
                    "itself contains marker lines, edit it with implement_file_with_deepseek."
                )
            else:
                replace.append(line)
    if state is not None:
        raise ToolError("Malformed reply: unterminated block.")
    if not blocks:
        raise ToolError(f"DeepSeek returned no SEARCH/REPLACE blocks:\n{reply[:400]}")
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
            raise ToolError(
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


@mcp.tool(title="Implement file with DeepSeek", annotations=WRITES_FILE)
async def implement_file_with_deepseek(
    ctx: Context,
    file_path: str,
    instruction: str,
    context_files: list[str] | None = None,
    reasoning_effort: Effort = "none",
    model: str = "",
) -> str:
    """
    Create a file, or replace an existing file entirely, with content written by DeepSeek.
    Returns the diff and an Undo command (these writes bypass Claude Code checkpoints).
    Nothing is written on any error.

    Args:
        file_path: Absolute path inside a git work tree.
        instruction: Full spec for the file: behavior, interfaces, constraints.
        context_files: Absolute paths of files DeepSeek should see (types, sister modules,
            tests). Keep the order stable across calls so DeepSeek's prompt cache hits.
        reasoning_effort: "none" (default, fastest and cheapest) when the instruction fully
            specifies the code. "low", "high" or "max" make DeepSeek think first, for
            algorithmic or loosely specified files.
        model: Model override; defaults to $DEEPSEEK_MODEL or deepseek-flash.
    """
    selected_model = model or DEFAULT_MODEL
    async with Call(
        ctx, "implement", file_path, selected_model, reasoning_effort
    ) as call:
        target = resolve_target(file_path)
        context = read_context(context_files or [])
        async with FILE_LOCKS[target]:
            current = read_current(target)
            forced = (
                {"tool_choice": FORCE_WRITE_FILE} if reasoning_effort == "none" else {}
            )
            reply = await call.complete(
                IMPLEMENT_SYSTEM,
                build_prompt(context, target, current, instruction),
                tools=[WRITE_FILE_TOOL],
                **forced,
            )
            content = file_content(reply).strip("\n")
            if not content:
                raise ToolError("DeepSeek returned empty content; nothing was written.")
            content += "\n"
            if current is not None and "\r\n" in current:
                content = content.replace("\r\n", "\n").replace("\n", "\r\n")
            change = save(target, current, content)
        return (
            f"Wrote {target} ({len(split_lines(content))} lines) with {call.summary()}. "
            f"{format_usage(reply.usage)}\n{change}"
        )


@mcp.tool(title="Patch file with DeepSeek", annotations=WRITES_FILE)
async def patch_file_with_deepseek(
    ctx: Context,
    file_path: str,
    instruction: str,
    context_files: list[str] | None = None,
    reasoning_effort: Effort = "none",
    model: str = "",
) -> str:
    """
    Edit an existing file with SEARCH/REPLACE blocks written by DeepSeek.
    All blocks apply or none do; each SEARCH must match exactly one run of whole lines.
    Returns the diff and an Undo command (these writes bypass Claude Code checkpoints).

    Args:
        file_path: Absolute path of an existing file inside a git work tree.
        instruction: What to change and why.
        context_files: Absolute paths of files DeepSeek should see (types, callers, tests).
            Keep the order stable across calls so DeepSeek's prompt cache hits.
        reasoning_effort: "none" (default, fastest and cheapest) when the instruction fully
            specifies the edit. "low", "high" or "max" make DeepSeek think first.
        model: Model override; defaults to $DEEPSEEK_MODEL or deepseek-flash.
    """
    selected_model = model or DEFAULT_MODEL
    async with Call(ctx, "patch", file_path, selected_model, reasoning_effort) as call:
        target = resolve_target(file_path)
        if not target.is_file():
            raise ToolError(
                f"'{target}' does not exist; use implement_file_with_deepseek to create it."
            )
        context = read_context(context_files or [])
        async with FILE_LOCKS[target]:
            current = read_file(target)
            reply = await call.complete(
                PATCH_SYSTEM, build_prompt(context, target, current, instruction)
            )
            blocks = parse_blocks(reply.content)
            patched = apply_blocks(current, blocks)
            change = save(target, current, patched)
        return (
            f"Patched {target}: {len(blocks)} block(s), now {len(split_lines(patched))} "
            f"lines, with {call.summary()}. {format_usage(reply.usage)}\n{change}"
        )


if __name__ == "__main__":
    mcp.run()
