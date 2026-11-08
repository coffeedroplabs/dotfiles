---
description: Execute the approved implementation plan with DeepSeek-V4.1-Flash writing the bulk code
argument-hint: [optional step or file filter]
allowed-tools: Bash(git status:*), Bash(git diff:*), mcp__deepseek-executor
---

Execute the approved implementation plan. You (Claude) orchestrate: plan, assemble context, review, verify. DeepSeek (`mcp__deepseek-executor`) writes the large, mechanical parts.

1. Pre-flight: run `git status` and confirm a clean tree or a topic branch. The executor refuses paths outside a git work tree.
2. List every file to create or modify, in dependency order. Filter by the arguments below if given.
3. For each file, choose who writes it:
   - Delegate when the code to generate is large and mechanical, roughly 80+ lines: new modules, tests, fixtures, repetitive refactors. Use `implement_file_with_deepseek` for a new file or full rewrite, `patch_file_with_deepseek` for targeted changes to an existing file.
   - Write it yourself with Edit/Write when the change is small, surgical or subtle. Describing such a change costs about as many tokens as writing it, and Edit keeps `/rewind` checkpoints, which executor writes bypass.
   - Pass absolute paths only. Put the types, schemas, sister modules and tests DeepSeek needs in `context_files`, in the same order across calls so DeepSeek's prompt cache hits.
4. After each executor call: read the `git diff` for that file, then run lint/typecheck, then the relevant tests. On failure, send the exact error back to DeepSeek. Stop after 3 attempts on one file and ask the user.
5. Finish with a concise summary: what changed, verification results, and the summed DeepSeek token usage from the tool results.

Additional instructions: $ARGUMENTS
