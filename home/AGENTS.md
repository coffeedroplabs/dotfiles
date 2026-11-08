# global agent instructions

- Use `gh-axi` for GitHub operations and `chrome-devtools-axi` for browser automation.
- State assumptions and surface ambiguities before writing code. If multiple interpretations exist, present tradeoffs rather than picking silently.
- When making technical decisions, do not give much weight to development cost. Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability. Avoid speculative complexity: write the minimum code needed to solve the problem without adding single-use abstractions or premature configurability.
- When doing bug fixes, always start with reproducing the bug in an E2E setting as closely aligned with how an end user would experience it as possible. This makes sure you find the real problem so your fix will actually solve it.
- When end-to-end testing a product, be picky about the UI you see and be obsessed with pixel perfection. If something clearly looks off, even if it is not directly related to what you are doing, try to get it fixed along the way.
- Apply that same high standard to engineering excellence: zero tolerance for lint errors, test failures, and test flakiness. If you see one, even if it is not caused by what you are working on right now, get it fixed.
- Comments must explain *why*, not restate what the code does. If a comment only duplicates the code below it, delete it instead of writing it. Keep comments only where they capture a non-obvious reason, constraint, or intent that the code alone cannot express.
- Do not mutate or delete existing comments or orthogonal code simply because they are not part of the current task.

## Behavioral Boundaries

### Always
- Plan before executing for multi-file changes or non-trivial workflows.
- Surface tradeoffs when multiple approaches exist.
- Keep context hygiene high: compact or clear when switching major tasks.

### Ask First
- Running destructive git actions (`git reset --hard`, `git push --force`, deleting branches).
- Introducing new external packages or modifying lockfiles without explicit instruction.
- Modifying machine-wide or system configurations outside project boundaries.

### Never
- Never use the em dash. Use plain dash - instead.
- When writing commit messages, NEVER auto-add your agent name as co-author.
- Never edit files marked auto-generated or runtime state (e.g. `CHANGELOG.md`, `herdr/*.log`, `herdr/*.sock`, `session.json`).

## Autonomous Execution & Evaluator Loop

- **Self-Verifying Evaluator Loop**: When implementing features or fixing bugs, run the project's automated test suite before reporting completion. If tests fail, diagnose and fix them iteratively. Never hand back broken code or ask the user to manually verify what tests can prove.
- **Worktree & Topic Branch Discipline**: Work inside topic branches or isolated git worktrees (`.worktrees/`). Keep commits atomic and self-contained.
- **Subagent Offloading**: When available, offload file searches, test runs, and deep log analysis to worker subagents to keep the main orchestrator context clean.
