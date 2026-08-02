# Private Group Scanner — Session State

**Updated:** 2026-08-02
**Repository:** `C:\Users\teqhv\fb scraper`
**Branch:** `main`
**Release state:** Phase 4 local candidate is verified; controlled APP release remains **REVISE**.

## Current position

The manager checkout contains the accepted local parser, capture, session-lifecycle, discovery-stop, and parity fixes through the current branch tip. The Phase 4G candidate now includes atomic progress, strict resume-target validation, duplicate-target rejection, canonical identifier-union hashing, the real one-Group callback adapter, and `batch-run --config` activation. It still has no accepted ten-Group APP receipt.

The current external operator root is `%LOCALAPPDATA%\private-group-scanner`. Session envelopes, browser profiles, raw captures, configs, exports, and receipts remain outside Git. No session values, account content, or private HTML are recorded here.

## Gate matrix

| Workstream | State | Evidence | Next action |
|---|---|---|---|
| T1 current-layout discovery and parser | Accepted locally | Focused fixture tests; reserved navigation routes are filtered; unsupported layouts stop fail-closed | Keep regression coverage |
| T2 Phase 4F one-Group APP proof | **REVISE** | Doctor 9/9 and session health ready; exactly one agent-managed Join request was submitted, then stopped at pending membership | Confirm membership or use an already-joined accessible Group, then rerun the complete one-Group receipt |
| T3 Phase 4G ten-Group workflow | Local candidate, gated | Sequential wrapper, callback adapter, target discovery API, CLI/config path, stop circuit breaker, and synthetic coverage are integrated | After accepted Phase 4F evidence, run the controlled ten-Group receipt |
| T4 independent release verification | Re-audit pending | Read-only audit found the prior APP and live-batch gates open; local post-integration checks now pass | Re-run the matrix after the next integrated APP evidence |

## Current external evidence

- `pgscan doctor` passed all nine checks at the exact external output, raw, and session roots.
- Imported and guided session health reached the authenticated route state.
- Normal-Chrome attach/finalize cleanup now leaves zero scanner-owned Chrome processes, no profile lock, no `DevToolsActivePort`, and no capture lock.
- The guided T2 stop receipt is outside Git at `exports\t2-guided-REVISE-d1beb55f-ab43-4024-ad6a-73a89fca81b5.json`; SHA-256 is `c47ee979d0eaa3d24ed7374ee7bb58d84f8a97dd88cf03440a8b20f81b5525ce`.
- The agent-managed T2 Join attempt is outside Git at `exports\t2-join-REVISE-b47d213b-84e8-4884-8a58-1bd9adb1e556.json`; SHA-256 is `7b4b0125adf9f7ec3671e717def03b756959dc9ed5e7ebec2b05c6edd4ac3fff`. The post-action control was `Cancel Request`, so membership was pending and the run stopped before capture.
- The latest manager discovery receipt is outside Git at `exports\a3087b32-a80b-4826-b81d-2e136f2cef42.operator-receipt.json`; SHA-256 is `858B815723FB315D0BB386251407997A1F3BCCB4A719FCCC96CF9C4B3E62FB98`.
- The latest discovery run found no supported joined Group candidate. It stopped before target selection, capture, export, replay, or further membership actions.
- Direct Group probes also found no post anchors or timestamps. These results are APP observations, not fixture proof of a successful collection.

## Local verification

- Focused Phase 4F parity tests pass for interrupted capture, resume, offline replay, and CSV/JSON/SQLite/manifest/Markdown parity.
- Focused Phase 4G workflow tests pass for deterministic ordering, recoverable interruption, incomplete-only resume, and aggregate metrics.
- Full suite: 254 passed; coverage 81.18% (2026-08-02).
- Ruff format, Ruff lint, and `ty` passed. The tracked-file secret scan returned zero findings. `pgscan doctor` passed 9/9.

## Remaining blockers

1. The submitted Join request is pending, so no membership-verified Group is available for the controlled one-Group run.
2. The required one-Group APP receipt is open. Capture, interruption/resume, offline replay, five-export parity, Comment reconciliation, and date-boundary evidence remain unproven against that controlled run.
3. Ten-Group execution remains gated until Phase 4F acceptance; the local adapter has tests but no live ten-Group receipt.
4. T4 needs a post-integration release re-audit, followed by final push parity.

## Operating boundary

- One visible browser worker; at most one Join action per controlled run, no duplicate Groups, and no posts, comments, likes, or messages.
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
uv run pgscan batch-run --config OPERATOR_CONFIG.toml
uv run pgscan doctor --output "$env:LOCALAPPDATA\private-group-scanner" --raw-root "$env:LOCALAPPDATA\private-group-scanner\raw" --session-root "$env:LOCALAPPDATA\private-group-scanner\sessions"
```

The next live attempt starts only after confirming zero scanner-owned browser processes and clean external profile locks. It must stop at the first unsupported page and write a redacted receipt.
