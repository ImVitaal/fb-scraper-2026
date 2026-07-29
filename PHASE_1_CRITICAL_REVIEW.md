# Phase 1 critical review

**Review date:** 2026-07-29  
**Reviewed file:** `PHASE_1_OPTIMAL_PLAN.md`  
**Verdict:** Good direction, but revision was required before fresh-session implementation.

## Critical findings

### P0 — Local repository state was missing

The workspace contains research files but is not a Git repository.

The plan did not tell a fresh session that:

- The private remote repository already exists.
- The local workspace has no `.git` directory.
- Project initialization and remote attachment must happen before implementation.

### P0 — Discovery implementation was undecided

The plan required automatic keyword-and-location discovery but specified only a replaceable adapter.

A fresh implementer still had to choose:

- The first discovery source.
- Its fallback behavior.
- How candidates are canonicalized.
- Whether live discovery is a release gate.

### P0 — Collection transport was undecided

“Public Page adapter” did not specify browser capture, HTTP capture, official API use, or another transport.

This decision affects fixtures, dependencies, session handling, pagination, and parser design.

### P1 — Hashing left two choices

“BLAKE3 or SHA-256” was not decision-complete.

Phase 1 should use SHA-256 because it is available in Python’s standard library and adequate for integrity and deduplication.

### P1 — Interactive-only CLI weakened reproducibility

One guided command matched the product answers, but tests and repeatable operations also require a non-interactive configuration mode.

The same command should support prompts and a committed example TOML configuration.

### P1 — Acceptance gates mixed fixture truth with live behavior

The 99% and 99.5% thresholds are meaningful only against labelled, fixed expectations.

Live Facebook counts can change during collection. The plan needed separate:

- Deterministic fixture release gates.
- Best-effort live smoke tests.

### P1 — Live candidate count was an unstable completion gate

“Discover at least five Page candidates” depends on search ranking, geography, connectivity, and source behavior.

The deterministic demonstration should use fixtures. A live campaign should be recorded as a smoke test rather than a hard release gate.

### P1 — Session security appeared before session scope

DPAPI and cookie preparation were included while Phase 1 deferred signed-in collection.

This created scope ambiguity. Cookie import belongs in the Group phase.

### P1 — Job and health states were not enumerated

Fresh sessions need exact state vocabularies to prevent incompatible implementations.

### P2 — Dependency and package decisions were missing

The plan did not choose:

- CLI framework.
- Schema library.
- Browser library.
- HTML parser.
- SQLite access strategy.
- Raw-capture compression format.

### P2 — Fresh-session reading order was missing

The workspace contains several overlapping research documents.

A new session needs a short source-of-truth order and explicit precedence.

## Corrections applied to Revision 2

Revision 2:

1. Records the remote and local repository state.
2. Defines a fresh-session bootstrap order.
3. Selects Python 3.12, Typer, Pydantic, Playwright, BeautifulSoup and standard-library SQLite.
4. Uses SHA-256 and gzip.
5. Selects a Playwright public capture adapter plus replay adapter.
6. Defines a DuckDuckGo HTML discovery adapter with CSV/URL fallback.
7. Separates fixture release gates from live smoke tests.
8. Adds non-interactive TOML execution.
9. Defines job and collection-health states.
10. Defers all cookie work.
11. Adds exact repository structure, commands, outputs and completion receipts.

