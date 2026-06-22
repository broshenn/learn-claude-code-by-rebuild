# Test Project Rules

@./.Codex/rules/chinese-greeting.md

This is a test project for mini-Codex feature validation.

## Rebuild Tutorial Workflow

When working on the step-by-step Python rebuild in `python-rebuild/`, update one chapter at a time and leave the resulting code changes uncommitted by default. After each chapter, report the changed files and remind the user that their editor can show the colored Git diff in Source Control. Only run `git add`, `git commit`, or `git push` when the user explicitly asks to commit, upload, or push.

Before implementing each rebuild chapter, compare the planned changes against the corresponding original project files under `python/mini_claude/` and keep the teaching implementation aligned with the original architecture instead of inventing unrelated code.

When the user says they are ready to start the next chapter, first commit and push the completed previous chapter changes, then implement the next chapter and leave those new changes uncommitted so the user can inspect the colored Git diff in their editor.
