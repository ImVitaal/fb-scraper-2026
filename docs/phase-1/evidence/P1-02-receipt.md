# P1-02 evidence receipt

## Working-tree identity

- Repository: `C:\Users\teqhv\fb scraper`
- Branch: `main`
- Baseline commit: `959768ad5012058a175090ebf02df28352fdacf4`
- Dependency: P1-01 complete at `959768a`
- Scope: P1-02 contracts, states, migrations, repositories, tests, and records

## TDD receipts

The first focused test run failed during collection:

```text
ModuleNotFoundError: No module named 'app.contracts'
```

The related-record integration test then failed before repository expansion:

```text
AttributeError: 'CanonicalRepository' object has no attribute 'save_post'
```

Minimal implementations followed each failing test. The final suite passes.

## Exact commands and results

| Command | Result |
|---|---|
| `uv sync --locked --all-groups` | PASS; 56 packages checked |
| `uv run ruff format --check .` | PASS; 28 files formatted |
| `uv run ruff check .` | PASS |
| `uv run ty check` | PASS |
| `uv run pytest -q` | PASS; 12 passed; 90.46% coverage |
| `uv build` | PASS; wheel and source distribution built |
| Wheel ZIP content assertion for `app/storage/migrations/001_initial.sql` | PASS |
| Clean temporary Python 3.12 environment wheel install and `Database.migrate()` | PASS |
| `uv run pip-audit` | PASS; no known dependency vulnerabilities |
| `uv run detect-secrets scan --all-files --exclude-files '(^|[\\/])(\.venv|\.pytest_cache|\.ruff_cache|\.ty|dist|build|htmlcov)([\\/]|$)'` | PASS; empty results |

## Artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `dist/private_group_scanner-0.1.0-py3-none-any.whl` | 14905 | `B4A4C2AA280D0EEB25D878635AEE6778FC4B1B187C2D017D41641605B831C03E` |
| `dist/private_group_scanner-0.1.0.tar.gz` | 11630 | `0F6BEB3DA8AC4B29262A9A7EE1157B5F03EAADC0CC038163EC1677CBCBEEB793` |
| `migrations/001_initial.sql` | — | `CD1539B90A0931D58EDFE99C263076E7E3B0BDCA100E9E4874BC472C98D560B2` |
| `src/app/storage/migrations/001_initial.sql` | — | `CD1539B90A0931D58EDFE99C263076E7E3B0BDCA100E9E4874BC472C98D560B2` |

## Acceptance-gate mapping

- **Versioned contracts:** strict Pydantic v2 Group, Post, Comment, evidence,
  provenance, null-reason, media, and observation models pass validation tests.
- **State vocabularies:** work-item, job, collection-health, and session classes
  are explicit.
- **SQLite schema:** migration 001 creates every required Phase 1 persistence
  category with foreign keys, checks, uniqueness constraints, and indexes.
- **Migration round-trip:** first apply returns version 1; repeated and reopened
  applications are no-ops.
- **Installed operation:** the built wheel contains migration 001 and applies it
  from a clean temporary Python 3.12 environment.
- **Repositories:** canonical record upserts preserve immutable counter history.
- **Job state:** allowed interruption and resume paths pass; terminal-state
  transitions fail explicitly.
- **Security:** capture metadata is immutable, raw bytes remain excluded, and
  the secret scan is empty.

## Limitations and open defects

No P1-02 defect remains. Raw-capture bytes, session encryption, capture parsing,
and orchestration are owned by later dependency-safe work items.
