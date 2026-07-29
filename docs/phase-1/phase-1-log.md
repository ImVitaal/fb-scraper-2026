# Phase 1 running log

## Current state

- Active plan: `LEAN_THREE_PHASE_COMPLETION_PLAN.md`
- Active milestone: 1C, live capture and resume
- Working tree baseline: `e400d45`
- Phase 2 remains blocked by the Phase 1 exit gate.

## Completed foundation

| Commit | Result |
|---|---|
| `bea7be1` | Aligned the private-Group product baseline |
| `959768a` | Added the Python package, CLI skeleton, quality tools, and CI |
| `f85d51a` | Added contracts, migrations, and repositories |
| `be6e541` | Closed migration, stale-write, identity, counter, UTC, and state-integrity defects |
| `7758507` | Adopted the lean three-phase execution plan |

## Latest verified baseline

- Tests: 25 passed.
- Coverage: 88.32%.
- Ruff: passed.
- `ty`: passed.
- Dependency audit: passed.
- Secret scan: passed.
- Built-wheel migration and integrity probes: passed.
- Current migrations: 001 and 002.

## Milestone 1A delivery

- Added one synthetic fixture with one Group, one Post, and one top-level Comment.
- `pgscan run --fixture ... --output ... --raw-root ...` stores deterministic gzip bytes,
  records and verifies SHA-256, persists canonical records, and exports JSON and CSV.
- `pgscan replay RUN_ID --offline --output ... --raw-root ...` verifies stored raw bytes,
  reparses them without network access, and returns the same canonical identifiers and
  normalized hash.
- Raw bytes use a separate operator raw root. The workflow rejects a raw root inside the
  repository and stores only a relative capture key in SQLite metadata.
- Fixture layout and version mismatches fail before SQLite persistence. Tampered gzip bytes
  fail replay integrity checks.

### Milestone 1A verification

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run pgscan run --fixture tests/fixtures/one_group_capture.json --output OUTPUT --raw-root RAW_ROOT
uv run pgscan replay RUN_ID --offline --output OUTPUT --raw-root RAW_ROOT
```

- Tests: 29 passed; coverage: 87.23%.
- Run and replay identifiers: `comment:comment-fixture-3001`,
  `group:group-fixture-1001`, and `post:post-fixture-2001`.
- Run and replay normalized hash:
  `724a34fa311918e89c43366861d5360b9ab902ebf8cd6973ed5f9a306f41a1a2`.

## Milestone 1B delivery

- Added current-user Windows DPAPI encrypted Playwright storage-state envelopes.
- Added imported state and visible guided-login session commands with equal non-secret metadata.
- Rejects session-root escape paths and validates encrypted-envelope hashes before browser use.
- Added direct URL and CSV fallback target workflows, one-target campaign selection, and idempotent selection retry.
- Added migration 003 session metadata and migration 004 target selection integrity.

### Milestone 1B verification

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

- Tests: 36 passed; coverage: 82.57%.
- Imported and guided session tests emit the same safe metadata keys.
- Direct URL and CSV tests select one durable target with no session data in command output.

## Next acceptance result

Milestone 1C must deliver a resumable controlled Group capture:

1. Collect posts within the 30-day boundary and all visible top-level comments.
2. Store each raw page before parsing and checkpoint before the next interaction.
3. Resume an interrupted run with the identical canonical identifier set.
4. Report unsupported layouts as non-success health states.

## In-progress 1C and 1D work

- Added a deterministic checkpoint-first pagination helper with page bounds and loop detection.
- Added strict keyword-and-location discovery parsing and durable discovery candidate selection.
- Live layout drift now preserves raw HTML, records `parser_drift`, and transitions the job to `failed`.
- Added JSON manifest, Markdown report, SQLite export-manifest receipt, and dry-run-by-default retention cleanup.
- The controlled browser Group capture, multi-page browser integration, TOML mode, measurements, and Phase 1 completion run remain open.

### Current verification

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

- Tests: 52 passed.
- Coverage: 81.56%.
- Ruff and `ty`: passed.
- Latest implementation commit: `9a0cf70`.
