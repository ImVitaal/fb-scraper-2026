# Phase 2 ten-Group completion report

**Date:** 2026-07-29
**Release class:** Synthetic-fixture reliability and measurement release

## Result

The Phase 2 fixture gate passes.

| Gate | Result |
|---|---|
| Explicit terminal states | 10 succeeded, 0 failed |
| Failure isolation | passed |
| Completed-Group preservation | passed |
| Resume incomplete Groups only | passed |
| Resume matches uninterrupted results | passed |
| Completeness | 100% |
| Duplicate identifiers | 0 |
| Selected worker limit | 1 |

## Measured fixture run

- Duration: 1.589256 seconds.
- CPU: 0.734375 seconds.
- Peak process memory: 51,060,736 bytes.
- Storage delta: 672,012 bytes.
- Retries: 0.
- Validated Posts: 10.
- Validated Comments: 10.
- Completeness-adjusted throughput: 755.070250 records per minute.

These values describe one local synthetic run. They are not product performance claims.

## Stable workload hashes

- Identifier-set SHA-256:
  `a7bd0be1d7f53a62a172b5ef9b4126caa1aefcd13d229699a73dddfd244af7c0`
- Normalized-set SHA-256:
  `7701d832c0eeb1f978f8ab8ec7805995cd36fd65ddd0d286423fd9b83ac0fe15`
- Measured receipt SHA-256:
  `db2cd833239cf8ca120ade06c4b9484543802afed758aec33bec118536bf87e3`
- Measured Markdown report SHA-256:
  `a56bef2ffb833ff1abcdcc5d3828875556c1c4f96965b589afd5c320875a38df`

## Commands

```powershell
uv run pgscan batch-run `
  --fixtures tests/fixtures/ten_groups `
  --output OUTPUT `
  --raw-root RAW_ROOT
uv run pgscan batch-run `
  --fixtures tests/fixtures/ten_groups `
  --resume `
  --output OUTPUT `
  --raw-root RAW_ROOT
uv run pytest tests/integration/test_phase2_batch.py
```

## Worker decision

The selected worker limit is one.

The sequential fixture workload completes quickly and deterministically.
No bounded-concurrency implementation was added without measured improvement evidence.
