# FB Scraper 2026 project instructions

## Fresh-session start

Before implementation:

1. Read `FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md`.
2. Read `PHASE_1_OPTIMAL_PLAN.md`.
3. Read `PHASE_1_CRITICAL_REVIEW.md`.
4. Confirm the repository, branch and current verification state.

Treat `PHASE_1_OPTIMAL_PLAN.md` as the Phase 1 implementation source of truth.

## Required skill sequence

Apply these installed skills during implementation:

1. `modern-python` — project setup, packaging, typing, and dependency practices.
2. `backend-patterns` — adapters, jobs, storage, schemas, and service boundaries.
3. `tdd-workflow` — write failing contract and behavior tests before implementation.
4. `python-testing` — fixtures, unit tests, replay tests, and integration tests.
5. `verification-loop` — run formatting, linting, types, tests, builds, and runtime checks.

Use these supporting skills when applicable:

- `coding-standards`
- `code-simplifier`
- `e2e-testing`
- `insecure-defaults`
- `git-cleanup`

## Product constraints

- Target native Windows.
- Use Python 3.12 or newer.
- Provide a guided command-line workflow.
- Keep the core product free and self-hosted.
- Do not require paid collection services.
- Support Pages, Groups, Events, and Posts first.
- Support keyword-and-location discovery.
- Collect the previous 30 days by default.
- Support up to 100 monitored targets.
- Store media metadata and source URLs.
- Export CSV and JSON.
- Append weekly snapshots.
- Retain local data for 90 days by default.

## Architecture rules

- Keep discovery, transport, capture, parsing, normalization, storage, intelligence, and export separate.
- Put every source integration behind an adapter contract.
- Store raw captures before parsing.
- Persist cursors before requesting the next page.
- Make retries idempotent.
- Use versioned schemas.
- Record field provenance and structured null reasons.
- Record explicit collection-health states.
- Keep cookie secrets outside datasets, logs, fixtures, and Git.
- Encrypt local session material.

## Quality gates

- Required identifier precision must equal 100%.
- Supported required-field accuracy must reach 99%.
- Pagination completeness must reach 99.5% on labelled fixtures.
- Duplicate canonical records must remain at or below 0.1%.
- Interrupted jobs must resume without record loss.
- Unsupported layouts must never be reported as successful collections.
- Raw replay must produce deterministic normalized output.

## Development workflow

1. Define or update the contract.
2. Add redacted fixtures.
3. Write failing tests.
4. Implement the smallest complete behavior.
5. Run Ruff formatting and linting.
6. Run type checks.
7. Run unit, replay, integration, and end-to-end tests.
8. Simplify the implementation without weakening tests.
9. Record verification results.
