---
description: Execute the active implementation plan using DeepSeek-V4.1-Flash as the code executor
argument-hint: [optional step or file filter]
allowed-tools: Bash(git status:*), Bash(git diff:*), deepseek-executor:*
---

Execute the active or approved implementation plan using DeepSeek-V4.1-Flash as the code executor.

Strict orchestrator protocol:
1. Pre-flight: Check `git status` to ensure a clean working tree or isolated topic branch before starting changes.
2. Review the plan steps and identify every file to be created or modified (filter by $ARGUMENTS if specific steps or files are targeted).
3. For each file in logical dependency order:
   - Collect necessary context (imports, types, schemas, sister modules, and relevant tests).
   - If creating a new file or completely rewriting a small file (<100 lines):
     Call `mcp__deepseek-executor__implement_file_with_deepseek(file_path, instruction, context_files)`.
   - If modifying an existing file (especially >100 lines):
     Call `mcp__deepseek-executor__patch_file_with_deepseek(file_path, instruction, context_files)`.
   - DO NOT write or replace code files over 15 lines directly using internal Write or Edit tools. DeepSeek must generate or patch the code.
   - Inspect the git diff to verify correctness and confirm no accidental deletions occurred.
   - Run linter / type-checking commands first for instant syntax and interface feedback.
   - Run the project's test suite to verify behavior.
   - If verification fails, feed the exact compiler or test error trace back into DeepSeek to fix (maximum 3 retry attempts per file before halting and requesting user guidance).
4. Present a concise summary of changes and test verification results once all steps pass.

Additional instructions: $ARGUMENTS
