/goal Complete the Phase 4 operator working release for `C:\Users\teqhv\fb scraper`.

# Current handoff

**Date:** 2026-07-30
**Branch:** `main`
**Active milestone:** Phase 4F controlled one-Group validation

## Verified implementation

- Phase 4A–4E implementation commits: `90a8a5b`, `ec3f3b1`, `5c15f56`, `8568625`, `98c515a`, `9a6ec4f`.
- Native doctor, session classification, persistent capture, APP extraction, discovery, resume, replay, inspection, and exports pass locally.
- Operator capture opens visibly by default.
- Browser import copies one selected closed profile and preserves its source.
- Each successful operator run writes a stable non-private receipt.
- Local imported and guided real-Chromium workflows pass.
- Real-browser interruption and resume identifiers match.
- Current suite: 140 passed with 82.08% coverage.
- Tracked-file secret findings: zero.

## Remaining work

1. Implement the simple pacing controls.
2. Import the saved Chrome `Default` session.
3. Discover and select the Groups.
4. Complete the controlled one-Group gate.
5. Complete the controlled ten-Group gate.
6. Refresh receipts and completion records.

Use:

```text
SESSION_METHOD=browser_profile
PROFILE_NAME=Default
KEYWORD=local community
LOCATION=London
```

Close the source browser before browser-profile import.
Keep private captures and session data outside Git.
Do not start Phase 4G or product expansion before the Phase 4F receipt passes.

Follow the minimal plan:

- `docs/phase-4/scraper-architecture-and-account-protection-plan.md`

The operator selected automatic Group discovery. Do not request Group URLs.

## Source of truth

Read `OPERATOR_WORKING_RELEASE_PLAN.md`, `SESSION_STATE.md`, and
`docs/phase-4/phase-4-log.md` before execution.
