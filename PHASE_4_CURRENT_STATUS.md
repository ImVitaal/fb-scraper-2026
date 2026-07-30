# Phase 4 current status

**Updated:** 2026-07-30  
**Repository:** `C:\Users\teqhv\fb scraper`  
**Branch:** `main`  
**Active milestone:** Phase 4F controlled one-Group validation — session attachment lead open

## Summary

The local Phase 4 operator release is implemented and verified.

The controlled APP one-Group and ten-Group gates still require an operator session and target.

## Completed implementation

### Phase 4A — preflight and session health

- Added native Windows runtime checks.
- Verified Python, package, migrations, Playwright, Chromium, DPAPI, and writable roots.
- Added ready, expired, challenged, restricted, and invalid session states.
- Added encrypted imported-session and guided-login workflows.

### Phase 4B — browser capture

- Kept one Playwright context for each run.
- Added bounded pages, interactions, retries, time, and storage.
- Stored each raw capture before extraction.
- Persisted checkpoints before the next browser interaction.
- Added post expansion, top-level comment expansion, scrolling, interruption, and resume.
- Made the operator browser visible by default.

### Phase 4C — extraction, discovery, and replay

- Added versioned APP HTML extraction.
- Extracted Group, Post, top-level Comment, and media records.
- Added provenance and structured null reasons.
- Enforced the 30-day Post boundary.
- Excluded comment replies.
- Added live keyword-and-location discovery.
- Added integrity-checked offline stored-HTML replay.

### Phase 4D and 4E — operator integration

- Connected capture and resume to multi-page Playwright operation.
- Routed replay by stored run type.
- Added detailed run inspection.
- Added CSV, JSON, standalone SQLite, manifest, and Markdown exports.
- Added a stable operator receipt.
- Added copied browser-profile import that preserves its source.

## Verified results

- Tests: **178 passed**.
- Coverage: **81.94%**.
- Ruff format: passed.
- Ruff lint: passed.
- `ty` type checking: passed.
- Native doctor checks: **9 of 9 passed**.
- Tracked-file secret findings: **0**.
- Local imported-session workflow: passed.
- Local guided-login workflow: passed.
- Real-browser interruption and resume: passed.
- Fixture run and offline replay normalized hashes: matched.
- Working tree was clean before this status file.

## Integration commits

- `90a8a5b` — operator preflight and session health.
- `ec3f3b1` — persistent browser capture.
- `5c15f56` — APP extraction, discovery, and replay.
- `8568625` — root operator workflow integration.
- `98c515a` — deterministic resume identity correction.
- `9a6ec4f` — operator receipts and visible capture defaults.
- `51e8dbd` — refreshed Phase 4 release evidence.
- `c811eb9` — Phase 4F protection evidence parity.
- `c7cf462` — scanner-owned persistent guided browser profile.
- `a83d92d` — guided session checkpoint stop record.
- `8de6e03` — guided-login rendering lead record.

The branch is nine commits ahead of `origin/main`. No release commit was pushed.

## Current external state

- The default scanner root has no ready encrypted session profile.
- Guided login reaches the account two-step route but renders only a persistent loading
  indicator. Two concurrent guided-login processes were stopped. No session envelope,
  discovery, membership change, capture, or export was created.
- The active runtime lead is `blocked_external_account_checkpoint`. The planned resolution is
  a normal Chrome attachment flow for first login, followed by automated reuse of its scanner-
  owned profile.
- No controlled target or operator TOML file is present.
- Chrome currently has active processes.
- Browser-profile import requires Chrome to be closed first.

## New account-protection review

Public scraper architectures and platform enforcement signals were reviewed.

The review found missing configurable pacing, cross-run budgets, cooldowns, and circuit-breaker coverage.

Implement these controls before the controlled operator run:

- `docs/phase-4/scraper-architecture-and-account-protection-plan.md`

## Remaining acceptance gates

### Phase 4F — controlled one-Group

1. Complete guided login and direct-URL collection.
2. Complete imported-session discovery and selection.
3. Interrupt one collection after a durable checkpoint.
4. Resume the interrupted collection.
5. Replay completed raw captures offline.
6. Verify identifiers, outputs, counts, limits, and receipt hashes.

### Phase 4G — controlled ten-Group

Start only after Phase 4F passes.

1. Run ten Groups sequentially.
2. Record explicit per-Group terminal states.
3. Inject one interruption and one recoverable failure.
4. Preserve completed Groups.
5. Resume only incomplete Groups.
6. Record duration, retries, CPU, memory, storage, completeness, and throughput.

## Selected operator bundle

```text
SESSION_PREPARATION=normal_chrome_attachment
PROFILE_NAME=operator
KEYWORD=local community
LOCATION=London
```

The operator delegated Group selection to the scanner.

The copied `Default` profile path remains incompatible with application-bound encryption.

## Next execution order

1. Implement and verify the normal Chrome attachment session path.
2. Complete account verification in that normal Chrome session.
3. Prepare and classify the encrypted session.
4. Run and verify the controlled one-Group workflow.
5. Record the Phase 4F receipt.
6. Run and verify the controlled ten-Group workflow.
7. Refresh the Phase 4 report and session state.
8. Commit the final verified evidence.

## Current release decision

Keep product expansion deferred.

Phase 4 completes only after the controlled one-Group and ten-Group receipts pass.
