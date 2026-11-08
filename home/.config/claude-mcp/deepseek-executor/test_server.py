# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=1.2.0,<2",
#     "openai>=1.40.0",
# ]
# ///
"""Offline tests for server.py with a stubbed DeepSeek client. Run: uv run --script test_server.py"""

import asyncio
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from openai.types import CompletionUsage

spec = importlib.util.spec_from_file_location(
    "server", Path(__file__).with_name("server.py")
)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class StubClient:
    def __init__(self, message: SimpleNamespace, finish_reason: str):
        self.calls = 0
        usage = CompletionUsage(
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            prompt_cache_hit_tokens=64,
            prompt_cache_miss_tokens=36,
        )
        choice = SimpleNamespace(message=message, finish_reason=finish_reason)
        self.response = SimpleNamespace(choices=[choice], usage=usage)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **_):
        self.calls += 1
        return self.response


class ExecutorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        (self.repo / ".git").mkdir()

    def stub(self, reply: str, finish_reason: str = "stop") -> StubClient:
        return self.install(
            SimpleNamespace(content=reply, tool_calls=None), finish_reason
        )

    def stub_write(
        self, content: str, finish_reason: str = "tool_calls", arguments: str = ""
    ) -> StubClient:
        call = SimpleNamespace(
            function=SimpleNamespace(
                name="write_file",
                arguments=arguments or json.dumps({"content": content}),
            )
        )
        return self.install(
            SimpleNamespace(content="", tool_calls=[call]), finish_reason
        )

    def install(self, message: SimpleNamespace, finish_reason: str) -> StubClient:
        client = StubClient(message, finish_reason)
        original = server.get_client
        server.get_client = lambda: client
        self.addCleanup(setattr, server, "get_client", original)
        return client

    def write(self, name: str, content: str) -> Path:
        path = self.repo / name
        path.write_bytes(content.encode())
        return path

    def patch(self, path: Path, **kwargs) -> str:
        return asyncio.run(
            server.patch_file_with_deepseek(str(path), "change it", **kwargs)
        )

    def implement(self, path: Path | str, **kwargs) -> str:
        return asyncio.run(
            server.implement_file_with_deepseek(str(path), "write it", **kwargs)
        )


def block(search: str, replace: str) -> str:
    replace_section = f"{replace}\n" if replace else ""
    return f"<<<<<<< SEARCH\n{search}\n=======\n{replace_section}>>>>>>> REPLACE\n"


class PatchTest(ExecutorTest):
    def test_deletion_followed_by_edit(self):
        path = self.write("a.py", "delete_me()\nold()\n")
        self.stub(block("delete_me()", "") + block("old()", "new()"))
        result = self.patch(path)
        self.assertIn("2 block(s)", result)
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
        self.assertIn("matched 2 times", self.patch(path))
        self.assertEqual(path.read_text(), "x = 1\nx = 1\n")

    def test_missing_search_writes_nothing(self):
        path = self.write("a.py", "keep()\nx = 1\n")
        self.stub(block("keep()", "kept()") + block("nope()", "y"))
        self.assertIn("matched 0 times", self.patch(path))
        self.assertEqual(path.read_text(), "keep()\nx = 1\n")

    def test_search_matches_whole_lines_only(self):
        path = self.write("a.py", "value = 1\n")
        self.stub(block("value = ", "x"))
        self.assertIn("matched 0 times", self.patch(path))

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
        self.assertIn("unterminated", self.patch(path))
        self.assertEqual(path.read_text(), "a\n")

    def test_marker_inside_replacement_is_rejected(self):
        path = self.write("a.rst", "Title\n")
        self.stub("<<<<<<< SEARCH\nTitle\n=======\nTitle\n=======\n>>>>>>> REPLACE\n")
        self.assertIn("inside a replacement section", self.patch(path))
        self.assertEqual(path.read_text(), "Title\n")

    def test_no_blocks(self):
        path = self.write("a.py", "a\n")
        self.stub("I could not do that.")
        self.assertIn("no SEARCH/REPLACE blocks", self.patch(path))

    def test_missing_file(self):
        self.stub(block("a", "b"))
        self.assertIn("does not exist", self.patch(self.repo / "nope.py"))

    def test_usage_is_reported(self):
        path = self.write("a.py", "a\n")
        self.stub(block("a", "b"))
        self.assertIn("cache hit 64, miss 36", self.patch(path))


class ImplementTest(ExecutorTest):
    def test_content_written_verbatim_including_fences(self):
        body = '"""Usage:\n\n```python\nmain()\n```\n"""\n\n\ndef main():\n    pass\n'
        self.stub_write(body)
        result = self.implement(self.repo / "gen.py")
        self.assertIn("(10 lines)", result)
        self.assertEqual((self.repo / "gen.py").read_text(), body)

    def test_reply_without_tool_call_writes_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub("x = 1\n</parameter>")
        self.assertIn("0 write_file calls", self.implement(path))
        self.assertEqual(path.read_text(), "original\n")

    def test_malformed_arguments_write_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub_write("", arguments='{"content": "x = ')
        self.assertIn("Malformed write_file arguments", self.implement(path))
        self.assertEqual(path.read_text(), "original\n")

    def test_truncated_reply_writes_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub_write("partial", finish_reason="length")
        self.assertIn("finish_reason='length'", self.implement(path))
        self.assertEqual(path.read_text(), "original\n")

    def test_empty_content_writes_nothing(self):
        path = self.write("a.py", "original\n")
        self.stub_write("\n\n")
        self.assertIn("empty content", self.implement(path))
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

    def test_write_file_tool_is_offered(self):
        client = self.stub_write("x = 1")
        captured = {}

        async def create(**kwargs):
            captured.update(kwargs)
            return client.response

        client.chat.completions.create = create
        self.implement(self.repo / "a.py")
        self.assertEqual(captured["tools"], [server.WRITE_FILE_TOOL])
        self.assertNotIn("tool_choice", captured)


class GuardTest(ExecutorTest):
    def test_relative_path_rejected(self):
        client = self.stub("x")
        self.assertIn("must be absolute", self.implement("rel/a.py"))
        self.assertEqual(client.calls, 0)

    def test_path_outside_git_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            client = self.stub("x")
            target = Path(outside) / "a.py"
            self.assertIn("not inside a git work tree", self.implement(target))
            self.assertFalse(target.exists())
            self.assertEqual(client.calls, 0)

    def test_missing_context_file_rejected_before_api_call(self):
        client = self.stub("x")
        missing = str(self.repo / "types.py")
        result = self.implement(self.repo / "a.py", context_files=[missing, "rel.py"])
        self.assertIn(missing, result)
        self.assertIn("rel.py", result)
        self.assertEqual(client.calls, 0)

    def test_context_files_are_sent(self):
        ctx = self.write("types.py", "class T: ...\n")
        client = self.stub_write("x = 1")
        captured = {}

        async def create(**kwargs):
            captured.update(kwargs)
            return client.response

        client.chat.completions.create = create
        self.implement(self.repo / "a.py", context_files=[str(ctx)])
        prompt = captured["messages"][1]["content"]
        self.assertIn(f'<file path="{ctx}">\nclass T: ...\n', prompt)


if __name__ == "__main__":
    unittest.main()
