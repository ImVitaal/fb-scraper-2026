# Private Group Scanner — Session State

**Updated:** 2026-08-02
**Repository:** `C:\Users\teqhv\fb scraper`
**Branch:** `main`
**Release state:** Phase 4 local candidate is verified; controlled APP release remains **REVISE**.

## Current position

The manager checkout contains the accepted local parser, capture, session-lifecycle, discovery-stop, and parity fixes through the current branch tip. The latest manager-owned Phase 4G addition is a bounded callback workflow for sequential target processing. It has local synthetic coverage, but it has no accepted ten-Group APP receipt or CLI activation evidence.

The current external operator root is `%LOCALAPPDATA%\private-group-scanner`. Session envelopes, browser profiles, raw captures, configs, exports, and receipts remain outside Git. No session values, account content, or private HTML are recorded here.

## Gate matrix

| Workstream | State | Evidence | Next action |
|---|---|---|---|
| T1 current-layout discovery and parser | Accepted locally | Focused fixture tests; reserved navigation routes are filtered; unsupported layouts stop fail-closed | Keep regression coverage |
| T2 Phase 4F one-Group APP proof | **REVISE** | Doctor 9/9 and session health ready; guided run stopped on repeated empty Group shells; current discovery stopped on `unsupported_discovery_layout` | Obtain a valid joined Group route and rerun the complete one-Group receipt |
| T3 Phase 4G ten-Group workflow | Local skeleton, gated | `OperatorBatchWorkflow` has focused synthetic coverage and per-target progress writes | After accepted Phase 4F evidence, wire the real one-Group resume callback, CLI/config path, atomic progress, and per-Group receipts |
| T4 independent release verification | Gated | Verification matrix prepared; final APP gates remain open | Run after integrated Phase 4F and Phase 4G candidate evidence |

## Current external evidence

- `pgscan doctor` passed all nine checks at the exact external output, raw, and session roots.
- Imported and guided session health reached the authenticated route state.
- Normal-Chrome attach/finalize cleanup now leaves zero scanner-owned Chrome processes, no profile lock, no `DevToolsActivePort`, and no capture lock.
- The guided T2 stop receipt is outside Git at `exports\t2-guided-REVISE-d1beb55f-ab43-4024-ad6a-73a89fca81b5.json`; SHA-256 is `c47ee979d0eaa3d24ed7374ee7bb58d84f8a97dd88cf03440a8b20f81b5525ce`.
- The latest manager discovery receipt is outside Git at `exports\2c3a1fd2-83bb-4418-ac0d-699fd802e828.operator-receipt.json`; SHA-256 is `D95E7AEE070D10258E8AA272D429A97B7C76FB21F5AE9EF761C3CD103D717667`.
- The latest discovery run found no supported joined Group candidate. It stopped before target selection, capture, export, replay, membership changes, and social actions.
- Direct Group probes also found no post anchors or timestamps. These results are APP observations, not fixture proof of a successful collection.

## Local verification

- Focused Phase 4F parity tests pass for interrupted capture, resume, offline replay, and CSV/JSON/SQLite/manifest/Markdown parity.
- Focused Phase 4G workflow tests pass for deterministic ordering, recoverable interruption, incomplete-only resume, and aggregate metrics.
- Full suite: 234 passed; coverage 81.17% (2026-08-02).
- Ruff format, Ruff lint, and `ty` passed. The tracked-file secret scan returned zero findings. `pgscan doctor` passed 9/9.

## Remaining blockers

1. The authenticated APP route exposed by the current session has no supported joined Group candidate and no usable post/timestamp layout.
2. The required one-Group APP receipt is therefore open. Resume, replay, five-export parity, Comment reconciliation, and date-boundary evidence remain unproven against that controlled run.
3. Ten-Group execution remains gated. The local wrapper is a skeleton, not a release receipt; it does not yet invoke the real one-Group resume path or the CLI/config surface.
4. Final push parity is pending the record commit and push verification.

## Operating boundary

- One visible browser worker; no membership actions and no social actions.
- Stop on unsupported layout, login/checkpoint, profile lock, restriction, or transport protection state.
- Keep private raw captures and session material outside the repository.
- Keep fixture/local evidence separate from authenticated APP evidence.

## Resume sequence

```powershell
Set-Location 'C:\Users\teqhv\fb scraper'
git status --short --branch
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run pgscan doctor --output "$env:LOCALAPPDATA\private-group-scanner" --raw-root "$env:LOCALAPPDATA\private-group-scanner\raw" --session-root "$env:LOCALAPPDATA\private-group-scanner\sessions"
```

The next live attempt starts only after confirming zero scanner-owned browser processes and clean external profile locks. It must stop at the first unsupported page and write a redacted receipt.
