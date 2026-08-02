# Phase 4 completion report

**Updated:** 2026-08-02
**Status:** **REVISE — local candidate verified; controlled APP one-Group gate open**
**Repository:** `C:\Users\teqhv\fb scraper`
**Branch:** `main`

## Executive result

The project now has a coherent local Phase 4 candidate and a fail-closed live stop path. The current authenticated APP session does not expose a supported joined Group candidate or usable post/timestamp content, so the required one-Group receipt is still open. Phase 4G and final release acceptance remain gated by that evidence.

No claim in this report promotes fixture or local-browser evidence to APP acceptance.

## Integrated work

- Normal-Chrome attachment now releases scanner-owned processes and profile locks after finalization.
- Discovery filters reserved navigation routes and stops when no valid Group candidate exists.
- Rendered Group headings and `[role="article"]` post containers are parsed on labelled fixtures.
- Repeated empty Group shells stop after the configured no-progress limit.
- Local one-Group parity covers interruption, resume, offline replay, and CSV/JSON/SQLite/manifest/Markdown outputs.
- `OperatorBatchWorkflow` provides a bounded sequential local skeleton with per-target progress writes, incomplete-only callback retry, recoverable-error handling, redacted target keys, and aggregate metrics. It is not wired to the real one-Group resume path or CLI/config surface.

## Acceptance matrix

| Gate | Result | Evidence |
|---|---|---|
| Native Windows, Python, roots, DPAPI/session contracts | Pass locally | Doctor and focused session tests |
| Normal-Chrome attachment cleanup | Pass locally and in external cleanup check | Zero scanner-owned processes and locks after cleanup |
| Rendered APP parsing | Pass on labelled redacted fixtures | Focused Phase 4C/T1 tests |
| Unsupported-layout handling | Pass | Current APP run stops with `unsupported_discovery_layout` |
| Raw-first capture and checkpoint behavior | Pass locally | Existing capture and parity tests |
| Interrupted run and resume identity parity | Pass locally | Phase 4F local parity test |
| Offline replay and five local export formats | Pass locally | Phase 4F local parity test |
| Phase 4G sequential batch wrapper | Local skeleton only | Three focused integration tests; no real one-Group adapter, CLI/config path, or live receipt |
| Controlled APP session preparation | Pass | Doctor 9/9; imported and guided health reached authenticated route |
| Controlled APP automatic joined-Group discovery | **Open** | No supported joined candidate in current route |
| Controlled APP one-Group capture | **Open** | No target selected; no capture receipt |
| Controlled APP resume/replay/export parity | **Open** | Depends on one-Group capture |
| Controlled APP ten-Group run | **Gated** | Depends on accepted one-Group receipt |
| T4 release verdict | **Gated** | Depends on accepted Phase 4F and Phase 4G evidence |

## External receipts

All paths below are outside Git and contain redacted operational evidence only.

| Evidence | Path | SHA-256 |
|---|---|---|
| Guided T2 stop | `%LOCALAPPDATA%\private-group-scanner\exports\t2-guided-REVISE-d1beb55f-ab43-4024-ad6a-73a89fca81b5.json` | `c47ee979d0eaa3d24ed7374ee7bb58d84f8a97dd88cf03440a8b20f81b5525ce` |
| Current manager discovery stop | `%LOCALAPPDATA%\private-group-scanner\exports\2c3a1fd2-83bb-4418-ac0d-699fd802e828.operator-receipt.json` | `D95E7AEE070D10258E8AA272D429A97B7C76FB21F5AE9EF761C3CD103D717667` |
| Route probe | `%LOCALAPPDATA%\private-group-scanner\route-probe-manager-20260802.json` | `0adf3a594fec81c57f3aa786d6b4c42d7715368b120dd1b9ed927a4645e8cacc` |
| Discovery query probe | `%LOCALAPPDATA%\private-group-scanner\discovery-query-probe-20260802.json` | `b82239acf1baefcd71217eeb4be523ec96912310ffa3e0856da5cc23fb59279e` |
| Direct Group probe | `%LOCALAPPDATA%\private-group-scanner\phase4f-direct-probe-20260802\receipt.json` | `f702afe700c33afaf34f7e74f5b6beb23a51ddb3788d7e37da4fae067afbf2cd` |

The earlier profile-lock stop remains historical evidence at `%LOCALAPPDATA%\private-group-scanner\t2-phase4f-stop-20260801.json` with SHA-256 `789d40266a0a1186daa987fb414f37b659c4d67ad914ae3e2e9224667a21c6a21`. The lifecycle repair and later cleanup supersede that blocker; the APP discovery gate remains open for a different reason.

## Quality gate record

The full local suite and final local release commands were run after this record update.

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
$files = @(git ls-files)
uv run detect-secrets scan $files
git diff --check
```

- Full suite: **234 passed** in 309.83 seconds; coverage **81.17%** (80% threshold met).
- Ruff format, Ruff lint, and `ty` passed. The tracked-file secret scan returned zero findings. `pgscan doctor` passed 9/9. Git checks passed before commit.
- A clean Git tree and `origin/main` parity are required.

## Release decision

**REVISE.** The local implementation is ready for the next controlled attempt, but the external APP route currently returns a shell without a supported joined Group candidate. Keep the one-Group gate closed. Do not activate ten-Group collection or report a Phase 4 release until a redacted APP receipt proves automatic selection, visible capture, interruption/resume, offline replay, five-export parity, Comment reconciliation, and date-boundary behavior.

## Next controlled attempt

1. Confirm zero scanner-owned Chrome processes, profile singleton locks, `DevToolsActivePort`, and capture locks.
2. Run doctor and session health at the exact external roots.
3. Use the supported imported or guided session path.
4. Run keyword/location discovery with one visible worker.
5. Stop at the first unsupported shell or protection state and preserve a redacted receipt.
6. After a valid joined Group is exposed, run the full one-Group capture/resume/replay/export sequence.
7. Only then activate the sequential ten-Group candidate and T4 verification.
