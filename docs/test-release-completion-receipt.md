# Phases 1–3 test-release completion receipt

**Date:** 2026-07-29
**Branch:** `main`
**Baseline:** `8b18b18`

## Integration commits

- Phase 1: `94b80fb` — fixture-backed one-Group workflow.
- Phase 2: `0239aef` — ten-Group reliability and resume.
- Phase 3: the commit containing this receipt — direct fixture comparison.

## Final verification commands

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run pgscan run --fixture tests/fixtures/one_group_capture.json --output OUTPUT --raw-root RAW_ROOT
uv run pgscan replay RUN_ID --offline --output OUTPUT --raw-root RAW_ROOT
uv run pgscan batch-run --fixtures tests/fixtures/ten_groups --output OUTPUT --raw-root RAW_ROOT
uv run pgscan batch-run --fixtures tests/fixtures/ten_groups --resume --output OUTPUT --raw-root RAW_ROOT
uv run pgscan compare --first tests/fixtures/comparison/local-results.json `
  --second tests/fixtures/comparison/competitor-results.csv --output OUTPUT
uv run detect-secrets scan --all-files
```

## Final verified results

- Tests: 99 passed after the deterministic-manifest regression test.
- Run/replay identifier match: yes.
- Run/replay normalized SHA-256 match: yes.
- Ten-Group completed states: 10.
- Ten-Group failed states: 0.
- Ten-Group resume identifier-set hash match: yes.
- Comparison report input and output hashes: verified.
- Secret-scan findings: 0.

## Stable hashes

- Phase 1 run ID:
  `99c74d143b9fd027f4160500765ff201b2469ee722e7c4509622348cae815f11`
- Phase 1 normalized SHA-256:
  `724a34fa311918e89c43366861d5360b9ab902ebf8cd6973ed5f9a306f41a1a2`
- Phase 1 manifest SHA-256:
  `b52a5f370b6388aeba657fc6df2311323fa2b1bfa028762bd0e4c5b960eec6be`
- Phase 2 identifier-set SHA-256:
  `a7bd0be1d7f53a62a172b5ef9b4126caa1aefcd13d229699a73dddfd244af7c0`
- Phase 2 normalized-set SHA-256:
  `7701d832c0eeb1f978f8ab8ec7805995cd36fd65ddd0d286423fd9b83ac0fe15`
- Phase 3 local input SHA-256:
  `4ea49865a5a4717a5a49ff6a478275688a2a92b5016ab2defd101784775d24e5`
- Phase 3 comparison input SHA-256:
  `0b49762c96ef06a4a944ab22cc783c64e47745fd6af042015803f7a6154a5b77`
- Phase 3 report SHA-256:
  `1a1d32efed03328174d613728c8ab23e34e1881c93aa9232949e3f930b1f54e4`
- Phase 3 receipt SHA-256:
  `63312d796565e381472959181cba0394ebadd924752f3c713e3b26718d2dbeb3`

## Test-release limits

- Controlled operator browser-session validation remains environment-specific.
- Layout support remains versioned and fixture-gated.
- The release collects top-level comments only.
- Media downloads remain outside scope.
- Phase 2 performance values describe synthetic local fixtures.
- Phase 3 compares synthetic result fixtures, not named external services.
