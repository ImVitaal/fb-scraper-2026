# P1-02 critical review

**Reviewed commit:** `f85d51a`
**Review date:** 2026-07-29
**Scope:** Contracts, migrations, repositories, tests, packaging, and evidence
**Verdict:** Corrective implementation required before releasing P1-03.

## Review method

1. Re-read the Phase 1 contracts and persistence rules.
2. Trace every write, conflict, retry, migration, and validation path.
3. Add failing regression tests for each reproducible defect.
4. Implement the smallest bounded correction.
5. Simplify duplicate validation.
6. Run source, package, and installed-wheel verification.

## Confirmed findings

| ID | Priority | Finding | Consequence | Resolution |
|---|---:|---|---|---|
| CR-01 | P1 | `INSERT OR IGNORE` hid invalid capture metadata | Constraint failures could become secondary row-access errors | Validate hashes and report explicit immutable-metadata conflicts |
| CR-02 | P1 | Older records could overwrite newer canonical state | Retries could regress the current dataset | Reject stale observations before every upsert |
| CR-03 | P1 | Post and Comment parents were mutable during upsert | Canonical relationships could silently change | Enforce immutable parent identity |
| CR-04 | P1 | Applied migrations had no content integrity check | Edited or missing migration files were accepted | Record normalized SHA-256 checksums and verify name, order, presence, and content |
| CR-05 | P1 | Counter collisions used `INSERT OR IGNORE` | Conflicting evidence could disappear silently | Accept exact retries and reject conflicting observation keys |
| CR-06 | P2 | Aware timestamps retained arbitrary offsets | Text ordering and deterministic output could vary | Normalize every contract and repository timestamp to UTC |
| CR-07 | P2 | Null reasons could reference present or unknown fields | Provenance metadata could contradict record values | Enforce exact absent-field coverage |
| CR-08 | P2 | Version 1 models accepted other schema versions | A model could mislabel incompatible data | Fix the contract version to `1.0` |
| CR-09 | P2 | Several SQLite state columns accepted arbitrary values | Direct writes could bypass application enums | Add migration 002 state and health guards |
| CR-10 | P2 | Discovery hits accepted missing raw-capture identifiers | Evidence links could dangle | Add insert, update, and delete integrity guards |
| CR-11 | P2 | The migration mirror test named only migration 001 | Later package-copy drift would pass | Compare every repository and packaged SQL file |
| CR-12 | P2 | Raw-byte checksums changed across line endings | Equivalent migrations could fail cross-checkout verification | Normalize line endings before migration hashing |
| CR-13 | P3 | Reaction names could be blank | Counter metric names could become ambiguous | Reject empty reaction names and share one validator |

## Migration correction

Migration 001 remains unchanged.

Migration 002 upgrades existing version 1 databases. It:

- Rejects invalid session classes.
- Rejects invalid session health.
- Rejects invalid task states.
- Rejects invalid attempt health.
- Rejects dangling discovery-capture references.
- Restricts deletion of referenced captures.
- Rejects existing invalid rows during migration.

This preserves migration immutability and gives previous databases a forward
upgrade path.

## Implemented regression gates

- Modified applied migration rejection.
- Cross-line-ending checksum stability.
- Contiguous migration numbering.
- Version 1 to version 2 upgrade.
- Repository and packaged migration parity.
- Invalid SQLite state rejection.
- Dangling capture rejection.
- Stale canonical-record rejection.
- Parent-identity mutation rejection.
- Conflicting counter rejection with transaction rollback.
- Capture validation and immutable identity checks.
- UTC normalization.
- Exact null-reason validation.
- Version 1 schema enforcement.

## Deferred improvements

| Improvement | Owner |
|---|---|
| Busy timeouts and multi-process write scheduling | P1-09 |
| Full field-provenance completeness rules | P1-05 and P1-06 |
| URL and identifier canonicalization | P1-06 and P1-07 |
| Raw byte durability and cleanup | P1-03 |
| Session-envelope integrity and encryption | P1-04 |
| Migration backup and recovery operations | P1-09 and P1-10 |

These items require later contracts or orchestration. They do not reopen P1-02.
