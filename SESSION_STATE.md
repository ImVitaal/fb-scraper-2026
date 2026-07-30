# Private Group Scanner — session state

**Updated:** 2026-07-29
**Current release:** Lean fixture-backed Phases 1–3 test release
**Active plan:** `OPERATOR_WORKING_RELEASE_PLAN.md`

## Current state

- Branch: `main`.
- Baseline before this release: `8b18b18`.
- Phase 1 integration: `94b80fb`.
- Phase 2 integration: `0239aef`.
- Phase 3 integration: the commit containing this state file.
- Active milestone: Phase 4A, operator preflight and session health.
- Product expansion remains deferred until the operator working-release gate passes.

## Delivered

### Phase 1

- Imported, guided, and existing encrypted session workflows.
- Session-gated keyword-and-location discovery.
- Direct URL and CSV target fallbacks.
- One selected Group.
- Multi-page raw-first capture.
- Durable checkpoint before each next-page fetch.
- Interruption and resume with matching identifiers.
- Offline stored-HTML replay.
- CSV, JSON, standalone SQLite, manifest, and Markdown outputs.
- Run, resume, replay, retention, and quality receipts.
- Guided and strict TOML operator modes.

### Phase 2

- Ten synthetic Group fixtures.
- Sequential one-through-ten Group collection.
- Per-Group terminal states.
- Failure isolation.
- Incomplete-Group resume with completed-Group preservation.
- Aggregate resource and completeness-adjusted throughput report.
- Worker limit retained at one because concurrency lacked improvement evidence.

### Phase 3

- One direct JSON result fixture.
- One direct CSV result fixture.
- Completeness, duplicate, duration, throughput, and cost calculation.
- Input and output hashes.
- Unsupported-field recording.
- Separate measured-value and conclusion sections.

## Verification

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

- Final tests: 99 passed.
- Coverage remained above 80%.
- Secret scan: zero findings.
- External fixture run, replay, batch, batch resume, and comparison commands passed.

## Current operator gaps

- Live parsing still expects fixture-only `data-pgscan-*` markers.
- Operator discovery still reads a supplied fixture capture.
- CLI capture and resume still use the one-page path.
- CLI replay does not route live HTML runs to stored-HTML replay.
- Session health does not probe an authenticated APP route.
- Controlled one-Group and ten-Group operator runs remain open.

## Limits

- Run controlled operator browser-session validation in its target Windows environment.
- Keep private raw captures and session material outside Git.
- Do not treat synthetic comparison results as external product claims.
- Keep product expansion deferred.

See `OPERATOR_WORKING_RELEASE_PLAN.md`, `docs/test-release-completion-receipt.md`,
and the phase completion reports.
