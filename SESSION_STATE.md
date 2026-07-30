# Private Group Scanner — session state

**Updated:** 2026-07-30
**Current release:** Phase 4 local-browser release candidate
**Active plan:** `OPERATOR_WORKING_RELEASE_PLAN.md`

## Current state

- Branch: `main`.
- Baseline before this release: `8b18b18`.
- Phase 1 integration: `94b80fb`.
- Phase 2 integration: `0239aef`.
- Phase 3 integration: `96f3c6e`.
- Phase 4A integration: `90a8a5b`.
- Phase 4B integration: `ec3f3b1`.
- Phase 4C integration: `5c15f56`.
- Phase 4 root integration: `8568625`.
- Phase 4 resume correction: `98c515a`.
- Phase 4 operator receipt and browser defaults: `9a6ec4f`.
- Active milestone: Phase 4F, controlled one-Group validation.
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

### Phase 4A through 4E

- Native Windows doctor checks pass.
- Session health classifies ready, expired, challenged, restricted, and invalid.
- Guided login, storage-state import, and local Chromium-profile import use encrypted envelopes.
- One Playwright context persists across bounded capture interactions.
- Opaque checkpoints precede each browser action.
- APP extraction records Group, Post, top-level Comment, media, provenance, and null reasons.
- Live keyword-and-location discovery stores raw bytes before parsing.
- CLI capture and resume use multi-page browser capture.
- CLI replay routes live runs through integrity-checked stored HTML.
- Inspect reports pages, interactions, counts, health, failure class, and retries.
- Live success writes CSV, JSON, standalone SQLite, manifest, Markdown, and a stable operator receipt.
- Operator capture is visible by default; headless mode requires an explicit option.
- Browser import copies a selected closed profile and preserves its source.
- Local real-Chromium imported and guided workflows pass without replacing `_capture_selected`.
- A real-Chromium interruption resumes with matching identifiers.

### Phase 4F account-protection gate

- One active operator capture is enforced through an exclusive local lock.
- A successful different-Group capture enforces the 900-second pause.
- Navigation, scrolling, expansion, and retry delays use protected configurable bounds.
- Live discovery and Group capture stop on account warnings and HTTP 401, 403, or 429.
- The first controlled Group has a hard 30-Post normalized and interaction ceiling.
- Later runs omit known Posts from normalization and record their skip count.
- Operator receipts record pacing, retries, inter-Group waits, skips, and stop reasons.
- Automatic discovery selects the lowest measured activity among joined results.

## Verification

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

- Final tests: 174 passed.
- Coverage: 81.58%.
- Tracked-file secret scan: zero findings.
- External fixture run, replay, batch, batch resume, and comparison commands passed.

## Current operator gaps

- A ready encrypted APP session is not present in the default session root.
- Chrome `Default` was closed and readable during the 2026-07-30 controlled attempt.
- Browser-profile import returned
  `browser profile did not contain an authenticated session`.
- The source database contained nine APP-domain rows: one session row and eight
  unexpired persistent rows.
- Playwright reported token decryption failures while launching the copied
  Chrome 150 profile.
- Treat copied-profile decryption as the current external runtime-compatibility
  prerequisite. The source profile remains unchanged.
- Automatic discovery found no joined Group matching the requested keyword and location.
- The controlled APP one-Group receipt remains open.
- The controlled ten-Group run must wait for the one-Group gate.

## Limits

- Run controlled operator browser-session validation in its target Windows environment.
- Keep private raw captures and session material outside Git.
- Do not treat synthetic comparison results as external product claims.
- Keep product expansion deferred.

See `OPERATOR_WORKING_RELEASE_PLAN.md`, `docs/test-release-completion-receipt.md`,
and `docs/phase-4/phase-4-completion-report.md`.
