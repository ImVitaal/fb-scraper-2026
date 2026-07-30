# Phase 4 completion report

**Date:** 2026-07-30
**Status:** Local release candidate complete; controlled APP gate pending
**Branch:** `main`

## Integration commits

- `90a8a5b` — operator preflight and session health.
- `ec3f3b1` — persistent browser capture.
- `5c15f56` — APP extraction, discovery, and replay.
- `8568625` — root operator workflow integration.
- `98c515a` — deterministic resume identity correction.

## Acceptance matrix

| Gate | Result |
|---|---|
| Windows, Playwright, Chromium, DPAPI, migrations, roots | Pass |
| Five explicit session states | Pass |
| Persistent real Playwright context | Pass |
| Raw-first capture | Pass |
| Checkpoint before browser interaction | Pass |
| APP Group, Post, top-level Comment, media extraction | Pass on labelled redacted fixtures |
| Thirty-day boundary | Pass on labelled redacted fixtures |
| Live discovery | Pass on local real-browser fixture |
| Imported and guided local workflows | Pass |
| Interruption and resume identifier parity | Pass |
| Offline replay parity | Pass |
| CSV, JSON, SQLite, manifest, Markdown | Pass |
| Unsupported layout false successes | 0 |
| Identifier precision | 100% on labelled fixtures |
| Supported required-field accuracy | 100% on labelled fixtures |
| Pagination completeness | 100% on labelled fixtures |
| Duplicate canonical records | 0% |
| Coverage | 81.61% |
| Tracked secret findings | 0 |
| Controlled APP one-Group | Pending |
| Controlled APP ten-Group | Blocked by one-Group gate |

## Working operator commands

```powershell
uv run pgscan doctor

uv run pgscan session import-browser `
  --profile operator `
  --browser-profile BROWSER_PROFILE_COPY `
  --channel chrome

uv run pgscan session health `
  --profile operator `
  --probe-url APP_AUTHENTICATED_URL

uv run pgscan run --config operator.toml
uv run pgscan inspect RUN_ID
uv run pgscan resume RUN_ID
uv run pgscan replay RUN_ID --offline
```

Use `uv run pgscan session login --profile operator` for guided login.

## Current decision

The local operator architecture is connected and verified with real Chromium.
The default session root contains no ready encrypted APP profile.
The controlled one-Group gate needs one operator-provided session and target bundle.
The ten-Group gate remains closed until that receipt passes.

## Limits

- APP selectors remain versioned and can report layout drift.
- Comment replies remain excluded.
- Media downloads remain excluded.
- The controlled APP and ten-Group metrics are not yet recorded.
- Product expansion remains deferred.

