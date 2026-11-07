# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mcp>=1.2.0,<2",
#     "openai>=1.40.0",
# ]
# ///
"""
DeepSeek Executor MCP Server for Claude Code Orchestrator.
Delegates heavy code generation, surgical patches, and file modifications to api.deepseek.com.
Powered by DeepSeek-V4.1-Flash (deepseek-flash) with prompt prefix caching.
"""

import logging
import os
import re
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

# Stdio safety: ensure all logging routes to stderr, never stdout
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("deepseek-executor")

mcp = FastMCP("deepseek-executor")

CONFIG_DIR = Path.home() / ".config" / "claude-mcp" / "deepseek-executor"
ENV_FILE = CONFIG_DIR / ".env"
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")


def load_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def get_client() -> OpenAI:
    api_key = load_api_key()
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is not set. Please set the DEEPSEEK_API_KEY environment variable "
            f"or put DEEPSEEK_API_KEY=your_key in {ENV_FILE}"
        )
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)


def extract_code_block(text: str, file_path: str) -> str:
    """
    Extract raw code from markdown fences if present.
    If multiple fenced blocks exist, select the longest code block to avoid preamble snippets.
    """
    text = text.strip()
    if file_path.endswith((".md", ".markdown")):
        return text

    blocks = re.findall(r"```(?:\w+)?\s*\n([\s\S]*?)\n```", text)
    if blocks:
        # Return the largest code block (by line count or char length)
        return max(blocks, key=len).strip()

    # Fallback: if output starts with fences but lacks clean trailing newline
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()

    return text


def build_context_blocks(context_files: list[str], base_dir: Path) -> str:
    blocks = []
    for ctx_path_str in context_files:
        ctx_p = Path(ctx_path_str)
        if not ctx_p.is_absolute():
            ctx_p = (base_dir / ctx_p).resolve()
        else:
            ctx_p = ctx_p.resolve()

        if ctx_p.exists():
            try:
                content = ctx_p.read_text(encoding="utf-8")
                blocks.append(f"--- Context File: {ctx_path_str} ---\n{content}\n")
            except Exception as e:
                blocks.append(f"--- Context File: {ctx_path_str} (read error: {e}) ---")
    return "\n".join(blocks)


@mcp.tool()
def implement_file_with_deepseek(
    file_path: str,
    instruction: str,
    context_files: list[str] | None = None,
    model: str = "",
    cwd: str = "",
) -> str:
    """
    Delegate full file creation or complete rewrite directly on disk to DeepSeek.
    Use this tool when creating a new file or rewriting a small file (<100 lines).
    For modifying existing files over 100 lines, use patch_file_with_deepseek instead.

    Args:
        file_path: Absolute or relative path to the file to create or rewrite.
        instruction: Detailed instructions, architecture spec, and requirements for the file.
        context_files: List of file paths containing relevant interfaces, schemas, or dependencies.
        model: Optional model override (defaults to 'deepseek-flash' / DeepSeek-V4.1-Flash).
        cwd: Optional working directory for resolving relative paths (defaults to current working directory).
    """
    try:
        client = get_client()
    except Exception as e:
        return f"Configuration Error: {e}"

    base_dir = Path(cwd).resolve() if cwd else Path.cwd()
    target = Path(file_path)
    if not target.is_absolute():
        target = (base_dir / target).resolve()
    else:
        target = target.resolve()

    selected_model = model or DEFAULT_MODEL
    actual_context_files = context_files if context_files is not None else []

    existing_content = ""
    if target.exists():
        try:
            existing_content = target.read_text(encoding="utf-8")
        except Exception as e:
            existing_content = f"<Could not read existing file: {e}>"

    joined_context = build_context_blocks(actual_context_files, base_dir)

    system_prompt = (
        "You are an expert software engineer executor working under a principal architect. "
        "Your role is to write clean, production-ready, bug-free, idiomatic code meeting "
        "all provided specifications. Output code directly without conversational preamble or notes."
    )

    # Prompt ordering optimized for DeepSeek 64-token Prefix Caching:
    # 1. System Prompt (static)
    # 2. Shared Context Files (static across multiple files in the same session)
    # 3. Target File & Existing Content
    # 4. Dynamic Instructions (tail)
    user_prompt = ""
    if joined_context:
        user_prompt += f"Supporting Context Files:\n{joined_context}\n\n"

    user_prompt += f"Target File: {file_path}\n\n"

    if existing_content:
        user_prompt += f"Existing Content (to be replaced):\n```\n{existing_content}\n```\n\n"

    user_prompt += f"Implementation Instructions:\n{instruction}\n\n"
    user_prompt += (
        "Generate the complete file content now. "
        "Preserve existing functionality unless explicitly instructed to change it. "
        "Ensure all imports, types, and logic are fully implemented without placeholders."
    )

    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as api_err:
        return f"DeepSeek API Error: {api_err}"

    generated_code = response.choices[0].message.content or ""
    cleaned_code = extract_code_block(generated_code, str(target))

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(cleaned_code, encoding="utf-8")
    except Exception as write_err:
        return f"Disk Write Error for {file_path}: {write_err}"

    line_count = len(cleaned_code.splitlines())
    return (
        f"Successfully implemented '{file_path}' using DeepSeek ({selected_model}).\n"
        f"Wrote {line_count} lines ({len(cleaned_code)} bytes). Ready for test verification."
    )


@mcp.tool()
def patch_file_with_deepseek(
    file_path: str,
    instruction: str,
    context_files: list[str] | None = None,
    model: str = "",
    cwd: str = "",
) -> str:
    """
    Surgically edit an existing file using DeepSeek search-and-replace blocks.
    Use this tool when modifying existing files (especially files over 100 lines)
    to prevent unintended deletions, loss of comments, or full-file regressions.

    Args:
        file_path: Absolute or relative path to the existing file to modify.
        instruction: Clear instructions specifying what changes to make.
        context_files: List of file paths containing relevant interfaces or types.
        model: Optional model override (defaults to 'deepseek-flash' / DeepSeek-V4.1-Flash).
        cwd: Optional working directory for resolving relative paths.
    """
    try:
        client = get_client()
    except Exception as e:
        return f"Configuration Error: {e}"

    base_dir = Path(cwd).resolve() if cwd else Path.cwd()
    target = Path(file_path)
    if not target.is_absolute():
        target = (base_dir / target).resolve()
    else:
        target = target.resolve()

    if not target.exists():
        return (
            f"Error: Target file '{file_path}' does not exist on disk. "
            "Use 'implement_file_with_deepseek' to create new files."
        )

    try:
        original_content = target.read_text(encoding="utf-8")
    except Exception as read_err:
        return f"Error reading '{file_path}': {read_err}"

    selected_model = model or DEFAULT_MODEL
    actual_context_files = context_files if context_files is not None else []
    joined_context = build_context_blocks(actual_context_files, base_dir)

    system_prompt = (
        "You are an expert software engineer executor performing precise surgical code edits.\n"
        "You must output one or more search/replace blocks in the exact format shown below:\n\n"
        "<<<<<<< SEARCH\n"
        "exact original lines to replace\n"
        "=======\n"
        "replacement lines\n"
        ">>>>>>> REPLACE\n\n"
        "Rules:\n"
        "1. Every SEARCH block must match the original file text character-for-character, including indentation and whitespace.\n"
        "2. Provide enough context lines in the SEARCH block to make each match unique within the file.\n"
        "3. Output ONLY SEARCH/REPLACE blocks. Do not add conversational text or code comments outside the blocks."
    )

    user_prompt = ""
    if joined_context:
        user_prompt += f"Supporting Context Files:\n{joined_context}\n\n"

    user_prompt += f"Target File: {file_path}\n\n"
    user_prompt += f"Current File Content:\n```\n{original_content}\n```\n\n"
    user_prompt += f"Modification Instructions:\n{instruction}\n\n"
    user_prompt += "Generate the SEARCH/REPLACE blocks now."

    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as api_err:
        return f"DeepSeek API Error: {api_err}"

    response_text = response.choices[0].message.content or ""

    # Parse search/replace blocks
    pattern = re.compile(
        r"<<<<<<< SEARCH\r?\n([\s\S]*?)\r?\n=======\r?\n([\s\S]*?)\r?\n>>>>>>> REPLACE",
        re.MULTILINE,
    )
    matches = pattern.findall(response_text)

    if not matches:
        return (
            f"Error: DeepSeek did not return any valid search/replace blocks for '{file_path}'.\n"
            f"Raw response preview:\n{response_text[:400]}"
        )

    current_content = original_content
    applied_count = 0

    for idx, (search_block, replace_block) in enumerate(matches, 1):
        if search_block not in current_content:
            # Fallback attempt: normalize line endings
            norm_search = search_block.replace("\r\n", "\n")
            norm_content = current_content.replace("\r\n", "\n")
            if norm_search in norm_content:
                current_content = norm_content.replace(norm_search, replace_block.replace("\r\n", "\n"), 1)
                applied_count += 1
                continue

            return (
                f"Patch Failure on block #{idx} in '{file_path}':\n"
                f"SEARCH text was not found in the target file.\n"
                f"Failed SEARCH snippet:\n```\n{search_block}\n```\n"
                "Please retry with additional surrounding context lines."
            )

        current_content = current_content.replace(search_block, replace_block, 1)
        applied_count += 1

    try:
        target.write_text(current_content, encoding="utf-8")
    except Exception as write_err:
        return f"Disk Write Error while saving patch for '{file_path}': {write_err}"

    new_line_count = len(current_content.splitlines())
    return (
        f"Successfully patched '{file_path}' using DeepSeek ({selected_model}).\n"
        f"Applied {applied_count} replacement block(s). File now has {new_line_count} lines. "
        "Ready for verification."
    )


@mcp.tool()
def generate_code_with_deepseek(
    instruction: str,
    context: str = "",
    language: str = "",
    model: str = "",
) -> str:
    """
    Delegate code generation or refactoring to DeepSeek API without writing directly to disk.
    Use this when you want to review the generated code block in-memory before writing.

    Args:
        instruction: What code, query, or script to generate.
        context: Supporting code, schemas, or constraints.
        language: Programming language (e.g., 'typescript', 'python', 'sql').
        model: Optional model override (defaults to 'deepseek-flash' / DeepSeek-V4.1-Flash).
    """
    try:
        client = get_client()
    except Exception as e:
        return f"Configuration Error: {e}"

    selected_model = model or DEFAULT_MODEL
    system_prompt = (
        "You are an expert developer executor. Generate high-quality, production-ready code "
        "following the exact specifications. Output code directly."
    )

    user_prompt = ""
    if context:
        user_prompt += f"Context:\n{context}\n\n"
    if language:
        user_prompt += f"Language: {language}\n\n"
    user_prompt += f"Task:\n{instruction}\n"

    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""
    except Exception as api_err:
        return f"DeepSeek API Error: {api_err}"


if __name__ == "__main__":
    mcp.run()
