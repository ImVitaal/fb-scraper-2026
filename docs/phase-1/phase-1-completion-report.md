# Phase 1 fixture-backed completion report

**Date:** 2026-07-29
**Release class:** Lean synthetic-fixture test release

## Result

The Phase 1 fixture gate passes.

- One Group completes session preparation, discovery, selection, capture, resume, replay, and export.
- Imported and guided session workflows produce the same safe metadata contract.
- Multi-page capture stores each raw page before parsing.
- Each next cursor becomes durable before its fetch.
- Interrupted and uninterrupted runs produce identical canonical identifiers.
- Offline HTML replay verifies raw hashes and reproduces the canonical identifier set.
- CSV, JSON, standalone SQLite, manifest, and Markdown outputs contain matching identifiers.
- Unsupported layouts, cursor loops, and page bounds produce terminal non-success states.
- Retention cleanup defaults to dry-run and enforces 30-day raw and 90-day normalized boundaries.

## Fixture quality evidence

| Gate | Measured result | Required result |
|---|---:|---:|
| Identifier precision | 100% | 100% |
| Required-field accuracy | 100% | at least 99% |
| Pagination completeness | 100% | at least 99.5% |
| Duplicate canonical records | 0% | at most 0.1% |
| Run/resume identifier match | yes | yes |
| Run/replay identifier match | yes | yes |
| Unsupported-layout false successes | 0 | 0 |
| Secret-scan findings | 0 | 0 |

The labelled tests use only synthetic Group, Post, Comment, discovery, and session fixtures.

## Verification

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run pgscan run --fixture tests/fixtures/one_group_capture.json --output OUTPUT --raw-root RAW_ROOT
uv run pgscan replay RUN_ID --offline --output OUTPUT --raw-root RAW_ROOT
uv run detect-secrets scan --all-files
```

- Tests: 91 passed.
- Coverage: 83.19%.
- Ruff formatting: passed.
- Ruff lint: passed.
- `ty`: passed.
- Secret scan: zero findings.

## Reproducible fixture hashes

- Fixture run ID:
  `99c74d143b9fd027f4160500765ff201b2469ee722e7c4509622348cae815f11`
- Run and replay normalized SHA-256:
  `724a34fa311918e89c43366861d5360b9ab902ebf8cd6973ed5f9a306f41a1a2`
- CSV SHA-256:
  `f925ca9226e30db119adbe9c94e34adfe662d9a459710f508e2adedc5f86d4f2`
- JSON SHA-256:
  `9ada119c7eb1cbde2cc15a3ad52b306d78d2ded7668aef8a7aa11ebee8b727f0`
- standalone SQLite SHA-256:
  `6801f3a11e2cb593e070ef221e56ae6f5148231370196c688fb4ac3d1ec23995`
- manifest SHA-256:
  `652a0b49a037a1905ec68af9a058734287b75984cb408573ad1abe79fab505c9`
- Markdown SHA-256:
  `31e1c66ec8f4d28909462bc392c143e51cd98fed35f36815a8bf99656e8f66b2`

## Test-release limits

- Browser rendering depends on the supported versioned layout anchors.
- The test release collects top-level comments only.
- Media downloads remain outside scope.
- Fixture collection uses one selected Group.
- A controlled operator browser-session run remains a separate environment-specific validation.
