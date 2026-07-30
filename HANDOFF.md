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

## Next phase — protected operator validation

### Mandatory account-protection gate

Complete these controls before any live Group collection:

1. Keep one worker and one active Group.
2. Add configurable delays before browser actions.
3. Use 10–20 seconds after navigation.
4. Use 6–12 seconds after scrolling.
5. Use 3–7 seconds after expansion.
6. Retry transient failures twice with 30-second and 120-second delays.
7. Stop immediately on login, checkpoint, CAPTCHA, lock, restriction, 401, 403, or 429.
8. Skip completed Posts during later runs.
9. Wait 15 minutes between Groups.
10. Record delays, retries, and stop reasons in the operator receipt.

Do not rotate accounts, cookies, proxies, fingerprints, or browser identities.

Require tests for pacing, stop conditions, known-Post skipping, and receipt redaction.

### Execution order

1. Implement and verify the account-protection gate.
2. Import the saved Chrome `Default` session.
3. Discover and select the Groups.
4. Run the lowest-volume valid Group first.
5. Review its receipt and session health.
6. Complete the controlled one-Group gate.
7. Complete nine remaining Groups sequentially.
8. Refresh receipts and completion records.

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
