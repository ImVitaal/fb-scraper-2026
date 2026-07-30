# Phase 4 execution log

**Date:** 2026-07-30
**Plan:** `OPERATOR_WORKING_RELEASE_PLAN.md`
**Status:** Phase 4A through 4E implemented; Phase 4F awaits one controlled APP input.

## Baseline

- Branch: `main`.
- Starting commit: `a781047`.
- Python: `3.12.13`.
- Package: `0.1.0`.
- Playwright: `1.61.0`.
- Chromium: installed at Playwright revision `1228`.
- Baseline: 99 tests, 83.41% coverage.

## Agent assignments and verified handbacks

| Lane | Owned paths | Verified result | Integration |
|---|---|---|---|
| Phase 4A | `src/app/session/`, `src/app/preflight.py`, unique tests | Preflight and five-state health passed | `90a8a5b` |
| Phase 4B | `src/app/capture/`, dynamic browser fixtures, unique tests | 9 real-Chromium tests passed | `ec3f3b1` |
| Phase 4C | parsing, discovery, HTML replay, redacted fixtures | 9 focused tests and scoped gates passed | `5c15f56` |
| Root | CLI, configuration, targets, live workflow, integration tests | Local vertical, exports, inspection, replay, resume, receipts passed | `8568625`, `98c515a`, `9a6ec4f` |

Root reviewed each diff and reran focused tests, Ruff, and `ty`.

## Implemented milestones

### 4A

- Added `pgscan doctor`.
- Verified Windows, Python, package, migrations, Playwright, Chromium, DPAPI, and storage roots.
- Added authenticated-route session classification.
- Added local Chromium-profile import.

### 4B

- Kept one context for the capture lifecycle.
- Added explicit browser failure states.
- Added Post and top-level Comment expansion.
- Added 30-day stop inputs.
- Added opaque integrity-checked interaction checkpoints.
- Added page, interaction, retry, time, and storage bounds.

### 4C

- Added versioned APP HTML extraction.
- Added canonical Group, Post, Comment, and media-source identities.
- Added field provenance and structured null reasons.
- Added reply exclusion and 30-day filtering.
- Added live discovery and explicit fixture discovery modes.

### 4D and 4E

- Stored live discovery raw bytes before parsing.
- Routed CLI capture and resume through `capture_pages`.
- Preserved imported and guided session provenance.
- Routed live replay through `StoredHtmlReplayWorkflow`.
- Generated CSV, JSON, standalone SQLite, manifest, and Markdown after live success.
- Added detailed `inspect` output.
- Fixed deterministic raw metadata during terminal-checkpoint resume.
- Added stable operator receipts with input, raw-set, normalized, export, metric, version, count, and limit evidence.
- Made operator browser capture visible by default.
- Changed browser import to copy one selected closed profile and preserve its source.

## Verification commands

```powershell
uv run pgscan doctor
uv run pgscan --help
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run pgscan run --fixture tests/fixtures/one_group_capture.json --output OUTPUT --raw-root RAW_ROOT
uv run pgscan replay RUN_ID --offline --output OUTPUT --raw-root RAW_ROOT
uv run detect-secrets scan (git ls-files)
```

## Verified results

- Doctor: ready; all nine checks passed.
- Tests: 140 passed.
- Coverage: 82.08%.
- Tracked-file secret findings: 0.
- Fixture run and replay identifiers match.
- Fixture normalized SHA-256:
  `724a34fa311918e89c43366861d5360b9ab902ebf8cd6973ed5f9a306f41a1a2`.
- Local real-browser run identifiers:
  `group:9100001`, `post:9200001`, `comment:9300001`.
- Local run duration: 0.481214 seconds.
- Local replay duration: 0.082885 seconds.
- Local completeness: 1.0.
- Local failures: 0.
- Local retries: 0.
- Local raw SHA-256:
  `f22c26a1fbc7109b0a75a45c01f8e814971ad9257fa399dae82e263dca373f9b`.
- Local JSON SHA-256:
  `96ca7a924317d44aaeb86893492ca5dbac6b8fba1af52f7f0511104d811f7471`.
- Local CSV SHA-256:
  `4cded91eb333141fcbc826d57ab221d0e27090a382fa1a0e882e5096941f6818`.
- Local SQLite SHA-256:
  `7bda0b33de751b84a9c87222a0b3aab805de268cebfca677b64d87a03673ef83`.
- Local manifest SHA-256:
  `34c04aff3155acecf8a8bbe946a7430c424b25cfe74392eb9ada0274ee5ead91`.
- Local Markdown SHA-256:
  `da53f03734c26fb6987712625aa6cf72d80fd692d778aa361a99d91ca71395a2`.
- Resume receipt SHA-256:
  `2411147a1ab4287f833a3d8f0b314ec9ac4ea3cbb820a8ee0ab8672df3aa1011`.
- Resume receipt normalized SHA-256:
  `d3ef2fcb3a94ec0daea14d6f2096c8230baced96d1a5ab6842405fe0ad4f407c`.
- Resume receipt raw-set SHA-256:
  `d31c6bc822ba789bd70927f06ecdefa8d94fc9e9f96b4f2d2ca2fd21a04f8393`.
- Resume receipt identifier-set SHA-256:
  `81fee44a4a671d6b8f44d80e0cf143a3e1dd319f27b5440463c5ad7a481d8503`.

## Gate status

- Local real-browser vertical: passed.
- Imported local workflow: passed.
- Guided local workflow: passed.
- Real-browser interruption and resume: passed.
- Phase 4F account-protection implementation: passed.
- Controlled APP one-Group: pending.
- Controlled APP ten-Group: not started because the one-Group gate is pending.

## Phase 4F protection checkpoint — 2026-07-30

- Enforced one active operator capture through an exclusive output-root lock.
- Enforced the 900-second pause after a successful different-Group capture.
- Added configurable navigation, scrolling, expansion, and retry delays.
- Added immediate stops for login, checkpoint, CAPTCHA, lock, restriction, 401, 403, and 429.
- Applied the same navigation, retry, and stop controls during live discovery.
- Limited the first controlled Group to 30 normalized Posts and bounded expansion actions.
- Pruned known Posts from later normalized captures and recorded skip counts.
- Added redacted success, capture-stop, and discovery-stop protection telemetry.
- Added automatic lowest-measured-volume selection for joined discovery results.
- Browser-profile copying excludes volatile extension and session directories while preserving its source.
- Ruff formatting, Ruff lint, and `ty` passed.
- Full suite: 174 passed with 81.58% coverage.
- Repository secret scan: zero findings.
- Doctor passed all nine checks.
- In-app discovery returned no joined Group matching `local community` and `London`.
- The source Chrome profile reopened and locked its cookie databases before import.
- No controlled Group collection occurred.
- Phase 4G remains gated.

## Remaining external input

Provide one controlled APP session and target bundle:

```text
SESSION_METHOD=guided|browser_profile
TARGET=GROUP_URL|KEYWORD+LOCATION
```

Private raw captures and session material must remain outside Git.

## Phase 4F controlled attempt — browser profile `Default`

The root agent ran the required sequence with external roots.

```powershell
uv run pgscan doctor `
  --output "$env:LOCALAPPDATA\private-group-scanner" `
  --raw-root "$env:LOCALAPPDATA\private-group-scanner\raw" `
  --session-root "$env:LOCALAPPDATA\private-group-scanner\sessions"

uv run pgscan session import-browser `
  --profile operator `
  --browser-profile "$env:LOCALAPPDATA\Google\Chrome\User Data" `
  --profile-name Default `
  --channel chrome `
  --output "$env:LOCALAPPDATA\private-group-scanner" `
  --session-root "$env:LOCALAPPDATA\private-group-scanner\sessions"

uv run pgscan session health `
  --profile operator `
  --probe-url "https://www.facebook.com/groups/" `
  --output "$env:LOCALAPPDATA\private-group-scanner" `
  --session-root "$env:LOCALAPPDATA\private-group-scanner\sessions"
```

Results:

- Branch and commit: `main`, `fd40d4d`.
- The initial worktree contained only the untracked one-shot prompt.
- The prompt is preserved in `stash@{0}`; the worktree was then clean.
- Doctor: ready; all nine checks passed.
- Chrome processes before import: zero.
- Import: failed with
  `browser profile did not contain an authenticated session`.
- Health: `invalid` with `session_state_invalid`; exit code 1.
- Source APP-domain metadata: nine rows; one session row, eight unexpired
  persistent rows, zero expired rows.
- Chrome 150 debug output reported token decryption failures in the copied
  profile.
- A focused attempt to retain the Windows password-store defaults did not
  change the runtime result. The temporary code and test were reverted.
- No encrypted `operator` profile was written.
- No discovery, target selection, Group capture, export, replay, or receipt ran.
- Account-stop conditions did not occur.
- Phase 4F remains pending. Phase 4G remains gated.

Exact gate result: copied Chrome `Default` profile decryption is the single
current runtime-compatibility blocker. Do not broaden target discovery.

## Phase 4F session-review corrections

The session review produced three focused product corrections.

1. Live discovery now distinguishes layout failure from no joined matching Group.
2. Application-bound copied profiles return a specific preparation diagnostic.
3. Success receipts reconcile visible expected and exported top-level Comments.

Discovery keeps membership changes separate from collection. Results displaying
Join controls are excluded. A missing joined match reports one explicit
membership prerequisite before target selection or capture.

Operator receipt schema `1.1` adds:

```json
{
  "comment_reconciliation": {
    "matched": true,
    "visible_top_level_comments_expected": 1,
    "visible_top_level_comments_exported": 1
  }
}
```

Focused verification:

```text
176 passed in 237.50s
Ruff: passed
ty: passed
```

## Phase 4F parity correction and root verification — 2026-07-30

Root reviewed the three bounded agent handbacks. The agents changed only their assigned
paths and made no commits.

- The browser Post ceiling is cumulative for one rendered capture. The 31st unique Post
  is removed before normalization even when it appears on a later page.
- A partial-stop receipt now hashes the durable Group, Post, and Comment identifier set.
  This keeps receipt evidence aligned with records saved before the immediate stop.
- Guided login remains the supported one-time preparation route when copied Chrome profiles
  use application-bound encryption. The later discovery and collection workflow uses the
  encrypted scanner session without manual browser collection.
- Guided login now uses a scanner-owned persistent Chrome profile outside the repository.
  Capture and resume reopen that same profile through the encrypted session metadata.

Root verification:

```powershell
uv run pgscan doctor --output "$env:LOCALAPPDATA\private-group-scanner" `
  --raw-root "$env:LOCALAPPDATA\private-group-scanner\raw" `
  --session-root "$env:LOCALAPPDATA\private-group-scanner\sessions"
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

Results:

- Doctor: all nine checks passed.
- Ruff format and lint: passed.
- `ty`: passed.
- Tests: 178 passed in 264.69 seconds; coverage 81.94%.
- Tracked-file secret scan: zero findings.
- The external `operator` session profile is still absent. No discovery, membership change,
  or live Group capture occurred during this verification step.

## Guided session stop — 2026-07-30

- The scanner-owned persistent Chrome profile reached an account verification checkpoint.
- The browser process was stopped immediately.
- No Group discovery, membership change, capture, export, replay, receipt, or session envelope
  was created from that attempt.
- The verification route and its parameters were not written to project records.

## Runtime lead — guided-login rendering failure

| Lead | Evidence | State | Next action |
|---|---|---|---|
| Scanner-owned Chrome reaches the account two-step route but renders only a persistent loading indicator. | Operator screenshot; repeated guided-login runs; no session envelope created. | `blocked_external_account_checkpoint` | Replace the Playwright-mediated first-login path with a normal Chrome attachment flow. Keep discovery and capture stopped. |

The screenshot itself remains outside the repository. No verification URL, code, token, or account content was copied into these records.

