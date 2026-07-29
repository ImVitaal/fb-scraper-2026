# Contributing

## Scope

Follow `AGENTS.md` and `PHASE_1_OPTIMAL_PLAN.md`.

Claim one `P1-XX` work item. Check every dependency before editing.

Do not start Phase 2 work before the Phase 1 exit gate passes.

## Workflow

1. Write a failing test.
2. Implement the smallest complete behavior.
3. Run `uv run ruff format .`.
4. Run `uv run ruff check .`.
5. Run `uv run ty check`.
6. Run `uv run pytest`.
7. Run `uv build`.
8. Record an evidence receipt.

## Data rules

Use synthetic or redacted fixtures.

Keep sessions, passwords, private captures, and exports outside Git.

