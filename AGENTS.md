# Private Group Scanner project instructions

## Fresh-session start

Before implementation:

1. Read `README.md`.
2. Read `FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md`.
3. Read `PHASE_1_OPTIMAL_PLAN.md`.
4. Read `PHASE_1_CRITICAL_REVIEW.md`.
5. Confirm the repository, branch, work-item state, and verification state.

Treat `PHASE_1_OPTIMAL_PLAN.md` as the Phase 1 implementation source of truth.

## Four-phase direction

1. Prove one correct and resumable private-Group workflow.
2. Scale it to ten Groups and optimize performance.
3. Run reproducible competitor comparisons.
4. Expand to other surfaces and intelligence features.

Do not begin a later phase before the current phase exit gate passes.

## Required skill sequence

Apply these installed skills during implementation:

1. `modern-python`
2. `backend-patterns`
3. `tdd-workflow`
4. `python-testing`
5. `verification-loop`

Use these supporting skills when applicable:

- `coding-standards`
- `code-simplifier`
- `e2e-testing`
- `insecure-defaults`
- `git-cleanup`

## Phase 1 product constraints

- Target native Windows.
- Use Python 3.12 or newer.
- Provide a guided command-line workflow.
- Keep the core free and self-hosted.
- Require no paid collection service, proxy, subscription, or cloud service.
- Support private Groups already visible through the operator session.
- Treat imported sessions and guided login as equal first-class workflows.
- Encrypt session material with Windows user-bound encryption.
- Never store account passwords.
- Require keyword-and-location Group discovery.
- Support direct URL and CSV fallback inputs.
- Collect one Group in the completion demo.
- Collect posts from the previous 30 days.
- Collect every visible top-level comment on matching posts.
- Defer comment replies.
- Store media metadata and source URLs.
- Export CSV, JSON, SQLite, manifest, and Markdown.
- Retain private raw captures for 30 days.
- Retain normalized local data for 90 days.

## Architecture rules

- Keep discovery, authentication, transport, capture, parsing, normalization,
  storage, and export separate.
- Put every integration behind an adapter contract.
- Store raw captures before parsing.
- Persist checkpoints before the next pagination interaction.
- Make retries idempotent.
- Use versioned schemas.
- Record field provenance and structured null reasons.
- Record explicit session and collection-health states.
- Keep session secrets outside datasets, logs, fixtures, exports, and Git.
- Fail closed when session decryption or integrity checks fail.
- Keep private raw captures outside the repository.

## Agent work rules

- Claim one bounded `P1-XX` work item.
- Check every dependency before action.
- Use disjoint owned paths for concurrent agents.
- Let the coordinator own shared contracts, migrations, and integration.
- Write failing tests before implementation.
- Implement the smallest complete behavior.
- Record exact commands and artifacts.
- Write the required evidence receipt.
- Mark completion only after acceptance gates pass.
- Do not broaden Phase 1 scope.
- Do not use live private content in committed tests.

## Quality gates

- Required identifier precision must equal 100%.
- Supported required-field accuracy must reach 99%.
- Pagination completeness must reach 99.5% on labelled fixtures.
- Duplicate canonical records must remain at or below 0.1%.
- Interrupted jobs must resume without record loss.
- Unsupported layouts must never report successful collection.
- Raw replay must produce deterministic normalized output.
- Session secrets present in fixtures, logs, exports, or Git must equal zero.
- The controlled one-Group demo must complete both session workflows.

## Development workflow

1. Claim the work item.
2. Define or update the contract.
3. Add redacted fixtures.
4. Write failing tests.
5. Implement the smallest complete behavior.
6. Run Ruff formatting and linting.
7. Run `ty` type checks.
8. Run unit, replay, integration, and end-to-end tests.
9. Simplify without weakening tests.
10. Record verification evidence.
