# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=2.3,<3",
#     "openai>=1.40.0",
# ]
# ///
"""Offline tests for server.py with a stubbed DeepSeek stream. Run: uv run --script test_server.py"""

import asyncio
import importlib.util
import json
import logging
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import anyio
import httpx2
import openai
from mcp import Client
from openai.types.chat import ChatCompletionChunk

spec = importlib.util.spec_from_file_location(
    "server", Path(__file__).with_name("server.py")
)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
# The SDK logs every failed tool call at INFO, and most calls here fail on purpose.
logging.getLogger().setLevel(logging.WARNING)

USAGE = {
    "prompt_tokens": 100,
    "completion_tokens": 20,
    "total_tokens": 120,
    "prompt_cache_hit_tokens": 64,
    "prompt_cache_miss_tokens": 36,
}


def halves(text: str) -> list[str]:
    """Split text in two so tests exercise accumulation across chunks."""
    middle = len(text) // 2
    return [part for part in (text[:middle], text[middle:]) if part]


def reply_chunks(
    content: str = "",
    arguments: str | None = None,
    finish_reason: str = "stop",
    reasoning: str = "",
) -> list[ChatCompletionChunk]:
    def chunk(delta=None, finish=None, usage=None) -> ChatCompletionChunk:
        choices = (
            []
            if delta is None
            else [{"index": 0, "delta": delta, "finish_reason": finish}]
        )
        return ChatCompletionChunk.model_validate(
            {
                "id": "chatcmpl-test",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "deepseek-flash",
                "choices": choices,
                "usage": usage,
            }
        )

    chunks = [chunk({"reasoning_content": part}) for part in halves(reasoning)]
    chunks += [chunk({"content": part}) for part in halves(content)]
    if arguments is not None:
        first, *rest = halves(arguments) or [""]
        chunks.append(
            chunk(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_0",
                            "type": "function",
                            "function": {"name": "write_file", "arguments": first},
                        }
                    ]
                }
            )
        )
        chunks += [
            chunk({"tool_calls": [{"index": 0, "function": {"arguments": part}}]})
            for part in rest
        ]
    chunks.append(chunk({}, finish_reason))
    chunks.append(chunk(usage=USAGE))
    return chunks


class StubStream:
    def __init__(self, client: "StubClient", chunks: list[ChatCompletionChunk]):
        self.client, self.chunks, self.closed = client, chunks, False

    async def __aenter__(self):
        self.client.active += 1
        self.client.max_active = max(self.client.max_active, self.client.active)
        if self.client.active >= self.client.hold_until_open:
            self.client.all_open.set()
        return self

    async def __aexit__(self, *exc):
        self.client.active -= 1
        self.closed = True

    async def __aiter__(self):
        self.client.streaming.set()
        await self.client.all_open.wait()
        for chunk in self.chunks:
            if self.client.delay:
                await asyncio.sleep(self.client.delay)
            yield chunk


class StubClient:
    """Stands in for AsyncOpenAI; each request streams the next scripted reply."""

    def __init__(self, replies: list[list[ChatCompletionChunk]]):
        self.replies = replies
        self.requests: list[dict] = []
        self.streams: list[StubStream] = []
        self.delay = 0.0
        self.active = self.max_active = 0
        self.streaming = asyncio.Event()
        # Streams wait until this many are open at once, so overlap is proven by
        # completion instead of inferred from timing.
        self.hold_until_open = 1
        self.all_open = asyncio.Event()
        self.error: BaseException | None = None
        self.on_request = lambda: None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs) -> StubStream:
        self.requests.append(kwargs)
        self.on_request()
        if self.error:
            raise self.error
        reply = self.replies[min(len(self.requests), len(self.replies)) - 1]
        stream = StubStream(self, reply)
        self.streams.append(stream)
        return stream

    @property
    def calls(self) -> int:
        return len(self.requests)


class ExecutorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve()
        # Undo saves pre-images with git hash-object, so this must be a real repository.
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.set(server, "LOG_FILE", self.repo / "state" / "calls.jsonl")

    def set(self, obj, name: str, value) -> None:
        self.addCleanup(setattr, obj, name, getattr(obj, name))
        setattr(obj, name, value)

    def install(self, *replies: list[ChatCompletionChunk]) -> StubClient:
        client = StubClient(list(replies))
        self.set(server, "get_client", lambda: client)
        return client

    def stub(self, *contents: str, finish_reason: str = "stop") -> StubClient:
        return self.install(
            *(reply_chunks(c, finish_reason=finish_reason) for c in contents)
        )

    def stub_write(
        self,
        content: str,
        finish_reason: str = "tool_calls",
        arguments: str = "",
        reasoning: str = "",
    ) -> StubClient:
        return self.install(
            reply_chunks(
                arguments=arguments or json.dumps({"content": content}),
                finish_reason=finish_reason,
                reasoning=reasoning,
            )
        )

    def write(self, name: str, content: str) -> Path:
        path = self.repo / name
        path.write_bytes(content.encode())
        return path

    def call(self, tool: str, path: Path | str, ok: bool, **args) -> str:
        async def run():
            async with Client(server.mcp) as client:
                return await client.call_tool(
                    tool, {"file_path": str(path), "instruction": "do it", **args}
                )

        result = asyncio.run(run())
        text = result.content[0].text
        self.assertEqual(result.is_error, not ok, text)
        # Claude Code prefers structured content over text, which would JSON-escape the diff.
        self.assertIsNone(result.structured_content)
        return text

    def patch(self, path: Path, **args) -> str:
        return self.call("patch_file_with_deepseek", path, True, **args)

    def patch_fails(self, path: Path, **args) -> str:
        return self.call("patch_file_with_deepseek", path, False, **args)

    def implement(self, path: Path | str, **args) -> str:
        return self.call("implement_file_with_deepseek", path, True, **args)

    def implement_fails(self, path: Path | str, **args) -> str:
        return self.call("implement_file_with_deepseek", path, False, **args)

    def log_records(self) -> list[dict]:
        return [json.loads(line) for line in server.LOG_FILE.read_text().splitlines()]


def block(search: str, replace: str) -> str:
    replace_section = f"{replace}\n" if replace else ""
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace_section}>>>>>>> REPLACE\n"


class PatchTest(ExecutorTest):
    def test_deletion_followed_by_edit(self):
        path = self.write("a.py", "delete_me()\nold()\n")
        self.stub(block("delete_me()", "") + block("old()", "new()"))
        self.assertIn("2 block(s)", self.patch(path))
        self.assertEqual(path.read_text(), "new()\n")

    def test_blocks_apply_in_order(self):
        path = self.write("a.py", "a = 1\nb = 2\nc = 3\n")
        self.stub(
            "Sure:\n```\n"
            + block("a = 1", "a = 10\na2 = 11")
            + block("c = 3", "c = 30")
            + "```"
        )
        self.patch(path)
        self.assertEqual(path.read_text(), "a = 10\na2 = 11\nb = 2\nc = 30\n")

    def test_non_unique_search_writes_nothing(self):
        path = self.write("a.py", "x = 1\nx = 1\n")
        self.stub(block("x = 1", "x = 2"))
        self.assertIn("matched 2 times", self.patch_fails(path))
        self.assertEqual(path.read_text(), "x = 1\nx = 1\n")

    def test_missing_search_writes_nothing(self):
        path = self.write("a.py", "keep()\nx = 1\n")
        self.stub(block("keep()", "kept()") + block("nope()", "y"))
        self.assertIn("matched 0 times", self.patch_fails(path))
        self.assertEqual(path.read_text(), "keep()\nx = 1\n")

    def test_search_matches_whole_lines_only(self):
        path = self.write("a.py", "value = 1\n")
        self.stub(block("value = ", "x"))
        self.assertIn("matched 0 times", self.patch_fails(path))

    def test_crlf_is_preserved(self):
        path = self.write("a.py", "one\r\ntwo\r\n")
        self.stub(block("one", "uno\nuno2"))
        self.patch(path)
        self.assertEqual(path.read_bytes(), b"uno\r\nuno2\r\ntwo\r\n")

    def test_missing_trailing_newline_is_preserved(self):
        path = self.write("a.py", "a\nlast")
        self.stub(block("last", "final"))
        self.patch(path)
        self.assertEqual(path.read_text(), "a\nfinal")

    def test_unterminated_block_is_rejected(self):
        path = self.write("a.py", "a\n")
        self.stub("<<<<<<< SEARCH\na\n=======\nb\n")
        self.assertIn("unterminated", self.patch_fails(path))
        self.assertEqual(path.read_text(), "a\n")

    def test_marker_inside_replacement_is_rejected(self):
        path = self.write("a.rst", "Title\n")
        self.stub("<<<<<<< SEARCH\nTitle\n=======\nTitle\n=======\n>>>>>>> REPLACE\n")
        self.assertIn("inside a replacement section", self.patch_fails(path))
        self.assertEqual(path.read_text(), "Title\n")

    def test_no_blocks(self):
        path = self.write("a.py", "a\n")
        self.stub("I could not do that.")
        self.assertIn("no SEARCH/REPLACE blocks", self.patch_fails(path))

    def test_missing_file(self):
        self.stub(block("a", "b"))
        self.assertIn("does not exist", self.patch_fails(self.repo / "nope.py"))

    def test_usage_is_reported(self):
        path = self.write("a.py", "a\n")
        self.stub(block("a", "b"))
        self.assertIn("cache hit 64, miss 36", self.patch(path))

    def test_identical_result_writes_nothing(self):
        path = self.write("a.py", "a\n")
        self.stub(block("a", "a"))
        self.assertIn("identical", self.patch_fails(path))


class ImplementTest(ExecutorTest):
    def test_content_written_verbatim_including_fences(self):
        body = '"""Usage:\n\n```python\nmain()\n```\n"""\n\n\ndef main():\n    pass\n'
        self.stub_write(body)
        self.assertIn("(10 lines)", self.implement(self.repo / "gen.py"))
        self.assertEqual((self.repo / "gen.py").read_text(), body)

    def test_reply_without_tool_call_writes_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub("x = 1\n</parameter>")
        self.assertIn("0 write_file calls", self.implement_fails(path))
        self.assertEqual(path.read_text(), "original\n")

    def test_malformed_arguments_write_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub_write("", arguments='{"content": "x = ')
        self.assertIn("Malformed write_file arguments", self.implement_fails(path))
        self.assertEqual(path.read_text(), "original\n")

    def test_truncated_reply_writes_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub_write("partial", finish_reason="length")
        self.assertIn("finish_reason='length'", self.implement_fails(path))
        self.assertEqual(path.read_text(), "original\n")

    def test_empty_content_writes_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub_write("\n\n")
        self.assertIn("empty content", self.implement_fails(path))
        self.assertEqual(path.read_text(), "original\n")

    def test_creates_parent_directories(self):
        self.stub_write("x = 1")
        self.implement(self.repo / "pkg" / "mod.py")
        self.assertEqual((self.repo / "pkg" / "mod.py").read_text(), "x = 1\n")

    def test_crlf_file_stays_crlf(self):
        path = self.write("a.py", "old\r\n")
        self.stub_write("new\nlines")
        self.implement(path)
        self.assertEqual(path.read_bytes(), b"new\r\nlines\r\n")

    def test_write_file_is_forced_without_thinking(self):
        client = self.stub_write("x = 1")
        self.implement(self.repo / "a.py")
        request = client.requests[0]
        self.assertEqual(request["tools"], [server.WRITE_FILE_TOOL])
        self.assertEqual(request["reasoning_effort"], "none")
        self.assertEqual(
            request["tool_choice"],
            {"type": "function", "function": {"name": "write_file"}},
        )

    def test_write_file_is_offered_unforced_with_thinking(self):
        # DeepSeek rejects a forced tool_choice in thinking mode with a 400.
        client = self.stub_write("x = 1", reasoning="plan the module")
        self.implement(self.repo / "a.py", reasoning_effort="high")
        request = client.requests[0]
        self.assertEqual(request["tools"], [server.WRITE_FILE_TOOL])
        self.assertEqual(request["reasoning_effort"], "high")
        self.assertNotIn("tool_choice", request)


class RequestTest(ExecutorTest):
    def test_request_streams_with_usage_and_full_output_budget(self):
        client = self.stub_write("x = 1")
        self.implement(self.repo / "a.py")
        request = client.requests[0]
        self.assertTrue(request["stream"])
        self.assertEqual(request["stream_options"], {"include_usage": True})
        self.assertEqual(request["max_tokens"], server.MAX_OUTPUT_TOKENS)
        self.assertTrue(client.streams[0].closed)

    def test_output_budget_leaves_room_for_a_large_prompt(self):
        self.assertEqual(server.max_tokens_for("x" * 3_000_000), 48_576)
        self.assertEqual(server.max_tokens_for("x" * 4_000_000), 8192)

    def test_api_error_is_a_tool_error(self):
        path = self.write("a.py", "a\n")
        client = self.stub(block("a", "b"))
        client.error = openai.APIConnectionError(
            request=httpx2.Request("POST", "https://api.deepseek.com")
        )
        self.assertIn("DeepSeek API error", self.patch_fails(path))
        self.assertEqual(path.read_text(), "a\n")

    def test_unexpected_exception_keeps_its_detail(self):
        path = self.write("a.py", "a\n")
        client = self.stub(block("a", "b"))
        client.error = RuntimeError("boom")
        self.assertIn("Unexpected RuntimeError: boom", self.patch_fails(path))

    def test_invalid_reasoning_effort_is_rejected(self):
        client = self.stub_write("x = 1")
        self.implement_fails(self.repo / "a.py", reasoning_effort="medium")
        self.assertEqual(client.calls, 0)


class ProtocolTest(ExecutorTest):
    def test_tools_carry_titles_annotations_and_effort_enum(self):
        async def run():
            async with Client(server.mcp) as client:
                return (await client.list_tools()).tools

        tools = {tool.name: tool for tool in asyncio.run(run())}
        self.assertEqual(
            set(tools), {"implement_file_with_deepseek", "patch_file_with_deepseek"}
        )
        for tool in tools.values():
            self.assertTrue(tool.title)
            self.assertFalse(tool.annotations.read_only_hint)
            self.assertTrue(tool.annotations.destructive_hint)
            self.assertFalse(tool.annotations.idempotent_hint)
            self.assertTrue(tool.annotations.open_world_hint)
            self.assertIsNone(tool.output_schema)
            properties = tool.input_schema["properties"]
            self.assertNotIn("ctx", properties)
            self.assertIn("none", json.dumps(properties["reasoning_effort"]))

    def test_progress_is_reported_while_streaming(self):
        self.set(server, "PROGRESS_INTERVAL", 0.0)
        self.stub_write("x = 1\n" * 50, reasoning="think it through")
        messages = []

        async def on_progress(progress, total, message):
            messages.append(message)

        async def run():
            async with Client(server.mcp) as client:
                return await client.call_tool(
                    "implement_file_with_deepseek",
                    {
                        "file_path": str(self.repo / "a.py"),
                        "instruction": "do it",
                        "reasoning_effort": "high",
                    },
                    progress_callback=on_progress,
                )

        self.assertFalse(asyncio.run(run()).is_error)
        self.assertTrue(messages)
        self.assertRegex(messages[-1], r"DeepSeek generated .*k chars \(.*k thinking\)")

    def test_cancel_closes_the_stream_and_writes_nothing(self):
        path = self.write("a.py", "a\n")
        client = self.stub(block("a", "b"))
        client.delay = 60

        async def run():
            async with Client(server.mcp) as mcp_client:
                with anyio.fail_after(10):
                    async with anyio.create_task_group() as tg:
                        tg.start_soon(
                            mcp_client.call_tool,
                            "patch_file_with_deepseek",
                            {"file_path": str(path), "instruction": "do it"},
                        )
                        await client.streaming.wait()
                        tg.cancel_scope.cancel()
                    # The cancel reaches the server as a notification; wait for it to land.
                    while not server.LOG_FILE.exists():
                        await asyncio.sleep(0.01)

        asyncio.run(run())
        self.assertEqual(client.calls, 1)
        self.assertTrue(client.streams[0].closed)
        self.assertEqual(path.read_text(), "a\n")
        self.assertEqual(self.log_records()[-1]["outcome"], "cancelled")


class WriteSafetyTest(ExecutorTest):
    def test_file_edited_during_generation_is_not_overwritten(self):
        path = self.write("a.py", "a\n")
        client = self.stub(block("a", "b"))
        client.on_request = lambda: path.write_text("edited\n")
        self.assertIn("changed while DeepSeek was generating", self.patch_fails(path))
        self.assertEqual(path.read_text(), "edited\n")

    def run_concurrently(self, *paths: Path) -> list:
        async def run():
            async with Client(server.mcp) as client:
                with anyio.fail_after(10):
                    return await asyncio.gather(
                        *(
                            client.call_tool(
                                "patch_file_with_deepseek",
                                {"file_path": str(p), "instruction": "do it"},
                            )
                            for p in paths
                        )
                    )

        return asyncio.run(run())

    def test_calls_on_one_file_run_one_after_the_other(self):
        path = self.write("a.py", "a = 1\nb = 2\n")
        client = self.stub(block("a = 1", "a = 10"), block("b = 2", "b = 20"))
        client.delay = 0.01
        results = self.run_concurrently(path, path)
        self.assertEqual([r.is_error for r in results], [False, False])
        self.assertEqual(client.max_active, 1)
        self.assertEqual(path.read_text(), "a = 10\nb = 20\n")

    def test_calls_on_different_files_run_concurrently(self):
        first = self.write("a.py", "a = 1\n")
        second = self.write("b.py", "b = 2\n")
        client = self.stub(block("a = 1", "a = 10"), block("b = 2", "b = 20"))
        client.hold_until_open = 2
        results = self.run_concurrently(first, second)
        self.assertEqual([r.is_error for r in results], [False, False])
        self.assertEqual(client.max_active, 2)

    def test_file_mode_is_kept(self):
        path = self.write("run.sh", "echo a\n")
        path.chmod(0o755)
        self.stub(block("echo a", "echo b"))
        self.patch(path)
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_new_file_gets_the_umask_mode(self):
        self.stub_write("x = 1")
        self.implement(self.repo / "a.py")
        mask = os.umask(0)
        os.umask(mask)
        self.assertEqual((self.repo / "a.py").stat().st_mode & 0o777, 0o666 & ~mask)
        self.assertEqual(list(self.repo.glob(".*.tmp")), [])

    def test_undo_restores_the_previous_content(self):
        path = self.write("my file.py", "a = 1\r\nb = 2\r\n")
        self.stub(block("a = 1", "a = 10"))
        result = self.patch(path)
        undo = next(line for line in result.splitlines() if line.startswith("Undo: "))
        subprocess.run(undo.removeprefix("Undo: "), shell=True, check=True)
        self.assertEqual(path.read_bytes(), b"a = 1\r\nb = 2\r\n")

    def test_undo_for_a_new_file_removes_it(self):
        self.stub_write("x = 1")
        target = self.repo / "new.py"
        self.assertIn(f"Undo: rm {shlex.quote(str(target))}", self.implement(target))


class ResultTest(ExecutorTest):
    def test_result_includes_the_diff(self):
        path = self.write("a.py", "a = 1\nb = 2\n")
        self.stub(block("a = 1", "a = 10"))
        result = self.patch(path)
        self.assertIn("Changes: +1 -1 lines.", result)
        self.assertIn("```diff\n", result)
        self.assertIn("\n-a = 1\n+a = 10\n b = 2\n```", result)

    def test_new_file_diff_is_against_dev_null(self):
        self.stub_write("x = 1\ny = 2")
        result = self.implement(self.repo / "a.py")
        self.assertIn("Changes: +2 -0 lines.", result)
        self.assertIn("--- /dev/null", result)

    def test_long_diff_is_replaced_by_stats(self):
        path = self.write("a.py", "".join(f"old_{i}\n" for i in range(300)))
        self.stub_write("".join(f"new_{i}\n" for i in range(300)))
        result = self.implement(path)
        self.assertIn("Changes: +300 -300 lines; the diff is too long to show", result)
        self.assertNotIn("```diff", result)

    def test_each_call_appends_one_log_record(self):
        path = self.write("a.py", "a\n")
        self.stub(block("a", "b"))
        self.patch(path)
        self.stub(block("missing", "b"))
        self.patch_fails(path)
        ok, error = self.log_records()
        self.assertEqual(ok["tool"], "patch")
        self.assertEqual(ok["file"], str(path))
        self.assertEqual(ok["effort"], "none")
        self.assertEqual(ok["outcome"], "ok")
        self.assertEqual(ok["finish_reason"], "stop")
        self.assertEqual(ok["cache_hit_tokens"], 64)
        self.assertEqual(error["outcome"], "error")
        self.assertIn("matched 0 times", error["error"])


class GuardTest(ExecutorTest):
    def test_relative_path_rejected(self):
        client = self.stub("x")
        self.assertIn("must be absolute", self.implement_fails("rel/a.py"))
        self.assertEqual(client.calls, 0)

    def test_path_outside_git_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            client = self.stub("x")
            target = Path(outside) / "a.py"
            self.assertIn("not inside a git work tree", self.implement_fails(target))
            self.assertFalse(target.exists())
            self.assertEqual(client.calls, 0)

    def test_missing_context_file_rejected_before_api_call(self):
        client = self.stub("x")
        missing = str(self.repo / "types.py")
        result = self.implement_fails(
            self.repo / "a.py", context_files=[missing, "rel.py"]
        )
        self.assertIn(missing, result)
        self.assertIn("rel.py", result)
        self.assertEqual(client.calls, 0)

    def test_context_files_are_sent(self):
        ctx = self.write("types.py", "class T: ...\n")
        client = self.stub_write("x = 1")
        self.implement(self.repo / "a.py", context_files=[str(ctx)])
        prompt = client.requests[0]["messages"][1]["content"]
        self.assertIn(f'<file path="{ctx}">\nclass T: ...\n', prompt)


if __name__ == "__main__":
    unittest.main()
