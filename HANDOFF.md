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

## Remaining gate

Complete one controlled APP Group using both session methods.
Then run the accepted workflow across ten Groups.

Provide one bundle:

```text
SESSION_METHOD=guided|browser_profile
PROFILE_NAME=Default|Profile 2|Profile 3
TARGET=GROUP_URL|KEYWORD+LOCATION
```

Close the source browser before browser-profile import.
Keep private captures and session data outside Git.
Do not start Phase 4G or product expansion before the Phase 4F receipt passes.

## Source of truth

Read `OPERATOR_WORKING_RELEASE_PLAN.md`, `SESSION_STATE.md`, and
`docs/phase-4/phase-4-log.md` before execution.
