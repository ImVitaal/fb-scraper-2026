# P1-02 critical-review evidence receipt

## Identity

- Repository: `C:\Users\teqhv\fb scraper`
- Branch: `main`
- Reviewed implementation: `f85d51a`
- Corrective baseline `HEAD`: `82662fa`
- Review: `docs/phase-1/reviews/P1-02-critical-review.md`

## Red tests

The new regression suite first failed during collection:

```text
ImportError: cannot import name 'CanonicalIdentityConflict'
```

The SQLite integrity test then proved the schema gap:

```text
Failed: DID NOT RAISE IntegrityError
```

The cross-line-ending test proved raw-byte migration hashes were unstable:

```text
MigrationError: applied migration 001 checksum mismatch
```

Each failure preceded its implementation correction.

## Final commands and results

| Command | Result |
|---|---|
| `uv sync --locked --all-groups` | PASS; 56 packages checked |
| `uv run ruff format --check .` | PASS; 31 files formatted |
| `uv run ruff check .` | PASS |
| `uv run ty check` | PASS |
| `uv run pytest -q` | PASS; 25 passed; 88.32% coverage |
| `uv build` | PASS |
| Wheel ZIP migration-content assertions | PASS; migrations 001 and 002 present |
| Isolated wheel install and migration | PASS; versions 1 and 2 applied |
| Installed-wheel integrity-guard probe | PASS |
| `uv run pip-audit` | PASS; no known dependency vulnerabilities |
| `uv run detect-secrets scan --all-files ...` | PASS; empty results |

## Artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `dist/private_group_scanner-0.1.0-py3-none-any.whl` | 17452 | `444286F6D23964F6A3745E78FF932CDF745872F6A7FDA3639E3E46F08C5D396F` |
| `dist/private_group_scanner-0.1.0.tar.gz` | 13724 | `F066D1A4317239EA6DE894DA8EA5ACDA31B56FB558E55A408406F3D8B00F1A05` |
| `migrations/001_initial.sql` normalized | — | `CD1539B90A0931D58EDFE99C263076E7E3B0BDCA100E9E4874BC472C98D560B2` |
| `migrations/002_integrity_guards.sql` normalized | — | `1DABD350937B137024D6606D239FD117C53B26DF92359C762D99C1156BA6ED50` |

Normalized migration hashes convert CRLF and CR line endings to LF before
hashing. Equivalent Windows and package copies therefore retain one identity.

## Closed gates

- Applied migration edits, renames, gaps, and missing files fail explicitly.
- Migration 001 remains immutable.
- Migration 002 upgrades existing version 1 databases.
- Exact retries remain idempotent.
- Conflicting capture and counter evidence fails explicitly.
- Stale records never replace newer current records.
- Post and Comment parent identities remain immutable.
- Contract and repository timestamps normalize to UTC.
- Null reasons match absent supported fields exactly.
- Direct SQLite writes cannot bypass guarded states or capture references.
- Every repository migration equals its packaged copy.

## Remaining limits

No P1-02 defect remains after this review. The review document assigns
orchestration, parsing, raw-byte, session, and canonicalization improvements to
their dependency-safe Phase 1 work items.
