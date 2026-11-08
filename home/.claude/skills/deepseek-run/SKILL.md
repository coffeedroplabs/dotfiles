---
name: deepseek-run
description: Execute an approved implementation plan with DeepSeek-V4.1-Flash writing the bulk code while Claude orchestrates, reviews and verifies
when_to_use: An implementation plan is approved and calls for roughly 80+ lines of large, mechanical code (new modules, tests, fixtures, repetitive refactors). Not for small, surgical or subtle changes.
argument-hint: [optional step or file filter]
allowed-tools: Bash(git status:*), Bash(git diff:*), mcp__deepseek-executor__implement_file_with_deepseek, mcp__deepseek-executor__patch_file_with_deepseek
---

Execute the approved implementation plan. You (Claude) orchestrate: plan, write briefs, review, verify. DeepSeek (`mcp__deepseek-executor`) writes the large, mechanical parts.

1. Pre-flight: run `git status` and confirm a clean tree or a topic branch. The executor refuses paths outside a git work tree.
2. List every file to create or modify, in dependency order. Filter by the arguments below if given.
3. For each file, choose who writes it:
   - Delegate when the code to generate is large and mechanical, roughly 80+ lines. Use `implement_file_with_deepseek` for a new file or full rewrite, `patch_file_with_deepseek` for targeted changes to an existing file.
   - Write it yourself with Edit/Write when the change is small, surgical or subtle. Describing such a change costs about as many tokens as writing it, and Edit keeps `/rewind` checkpoints, which executor writes bypass.
4. Brief DeepSeek so it has nothing to guess: exact interfaces and signatures, behavior and edge cases, constraints (libraries, style, what to leave alone) and acceptance criteria. Pass absolute paths only. Put the types, schemas, sister modules and tests it needs in `context_files`, in the same order across calls so DeepSeek's prompt cache hits.
5. Leave `reasoning_effort` at `none` when the brief fully specifies the code: it is several times faster and cheaper. Use `high` for algorithmic or loosely specified files, `max` only after `high` failed.
6. Independent files may be delegated in parallel; calls on the same file queue. A call running over 2 minutes moves to the background: do not review, test or edit its file until the result arrives.
7. After each call, review the diff in its result (run `git diff` only when the result says the diff is too long), then run lint/typecheck and the relevant tests. A failed call writes nothing and says why. On failure, send the exact error back to DeepSeek. Stop after 3 attempts on one file and ask the user. To discard a write, run the `Undo:` line from its result.
8. Finish with a concise summary: what changed, verification results, and the summed DeepSeek token usage from the tool results.

Additional instructions: $ARGUMENTS
