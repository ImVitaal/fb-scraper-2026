/goal Complete the Phase 4 operator working release for `C:\Users\teqhv\fb scraper`.

# One-shot handoff for the next Codex session

Use this complete prompt in a new Codex desktop session.

You are the root coordinator. Continue autonomously until the verified operator workflow works or one external interactive input remains.
Do not stop after planning, scaffolding, agent status, or fixture-only success.

## Objective

Connect the accepted fixture architecture to controlled APP browser operation.

Complete these results in order:

1. Verify Windows, Playwright, Chromium, DPAPI, migrations, and storage roots.
2. Classify an encrypted session as ready, expired, challenged, restricted, or invalid.
3. Capture one selected Group through a persistent Playwright context.
4. Store every raw page before extraction.
5. Persist each interaction checkpoint before the next click, expansion, or scroll.
6. Extract Group, Post, top-level Comment, and media metadata from APP captures.
7. Enforce the 30-day Post boundary.
8. Implement live keyword-and-location discovery.
9. Connect multi-page run, interruption, resume, offline replay, inspection, and every export.
10. Complete one controlled Group through imported and guided session workflows.
11. After the one-Group gate passes, repeat the accepted workflow across ten Groups.
12. Finish with verified receipts, hashes, commits, current documentation, and a clean working tree.

Do not start product expansion.
Do not add Pages, Events, scheduling, dashboards, cloud services, proxies, paid services, AI features, or another database.

## Mandatory startup

Read these files before edits:

1. `AGENTS.md`
2. `README.md`
3. `FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md`
4. `LEAN_THREE_PHASE_COMPLETION_PLAN.md`
5. `OPERATOR_WORKING_RELEASE_PLAN.md`
6. `docs/phase-1/phase-1-log.md`
7. `docs/test-release-completion-receipt.md`
8. `SESSION_STATE.md`
9. `pyproject.toml`
10. `git status`, `git log -5`, and the relevant source and tests

Treat `OPERATOR_WORKING_RELEASE_PLAN.md` as the current implementation source.

Current pushed baseline:

- Branch: `main`
- HEAD: `96f3c6e515b8bfc2adc565fb2831d19d58123663`
- Tests: 99 passed
- Coverage: 83.41%
- Ruff format, Ruff lint, and `ty`: passed
- Fixture run, replay, ten-Group batch, resume, comparison, and secret scan: passed

The working tree contains intentional uncommitted planning updates:

- `OPERATOR_WORKING_RELEASE_PLAN.md`
- `HANDOFF.md`
- `README.md`
- `SESSION_STATE.md`
- `FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md`
- `LEAN_THREE_PHASE_COMPLETION_PLAN.md`

Preserve and review these updates.
Commit them with the first verified integration milestone.

## Current truth

The fixture release is valid.
The complete operator workflow is not yet proven.

Known blockers:

- `src/app/parsing/live_group.py` accepts fixture-only `data-pgscan-*` markers.
- `src/app/discovery/session_fixture.py` reads a local fixture instead of APP.
- Operator integration tests patch `_capture_selected`.
- CLI capture and resume use one-page `capture_html`.
- CLI replay always selects `FixtureWorkflow.replay`.
- `StoredHtmlReplayWorkflow` is not routed from the CLI.
- Session health validates envelope integrity but not authenticated APP access.
- Live records are incorrectly labelled with `session_class="fixture"`.
- Imported sessions accept Playwright state JSON but do not import a supported local browser profile.
- Ten-Group collection remains fixture-only.

## Required skills

Apply this sequence:

1. `modern-python`
2. `backend-patterns`
3. `tdd-workflow`
4. `python-testing`
5. `verification-loop`

Use `coding-standards`, `code-simplifier`, `e2e-testing`, and `insecure-defaults` when applicable.

## Required Luna high orchestration

Use Luna side-window agents through the Codex desktop PowerShell terminal.

Start every Luna session from the repository:

```powershell
Set-Location "C:\Users\teqhv\fb scraper"
& "C:\Users\teqhv\.local\bin\luna.cmd"
```

The managed profile is:

```text
C:\Users\teqhv\.codex\luna-side-agent.config.toml
```

Require model `gpt-5.6-luna` with `high` reasoning.

Use `codex_app.read_thread_terminal` after each launch.
Verify the model, reasoning level, directory, assignment, progress, and completion.

Do not accept terminal status as evidence.
Verify every changed file, diff, test, artifact, and gate yourself.

Release work only when dependencies pass.
Keep owned paths disjoint.

### Luna agent A — preflight and session health

Own:

- `src/app/session/`
- new preflight modules outside `src/app/cli/`
- new session-health and preflight tests with unique filenames

Deliver:

- Windows runtime and dependency checks
- Chromium and Playwright checks
- DPAPI and writable-root checks
- authenticated-session probe
- ready, expired, challenged, restricted, and invalid classification
- imported and guided session parity
- zero secret material in output

Exclude:

- CLI integration
- configuration contracts
- migrations
- phase logs
- browser pagination
- parsing and discovery

### Luna agent B — browser capture contract

Own:

- `src/app/capture/`
- new Playwright browser-contract tests with unique filenames
- local dynamic browser fixtures required by those tests

Deliver:

- persistent browser context
- `RenderedPageCapture` implementation
- content-ready and failure-state detection
- Post and top-level Comment expansion
- 30-day scrolling stop inputs
- durable opaque next-action checkpoints
- bounded interactions, pages, retries, time, and storage
- deterministic interruption cleanup

Exclude:

- CLI integration
- `src/app/workflows/live_capture.py`
- parsing and discovery
- contracts and migrations
- phase logs

### Luna agent C — APP extraction, discovery, and replay

Own:

- `src/app/parsing/`
- `src/app/discovery/`
- `src/app/workflows/html_replay.py`
- new extraction, discovery, and replay tests with unique filenames

Deliver:

- one versioned APP extraction adapter
- canonical Group, Post, Comment, and media identifiers
- provenance and structured null reasons
- live keyword-and-location discovery adapter
- explicit fixture discovery test mode
- stored-HTML replay behavior for operator captures
- smallest redacted labelled fixtures

Exclude:

- CLI integration
- `src/app/workflows/live_capture.py`
- session code
- contracts and migrations
- phase logs

## Root coordinator ownership

Root owns:

- `src/app/cli/main.py`
- `src/app/configuration.py`
- shared contracts
- migrations
- `src/app/workflows/live_capture.py`
- full operator integration tests
- phase logs and receipts
- integration verification
- Git commits

Root must:

1. Write or approve failing behavior tests before implementation.
2. Integrate Luna work only after independent verification.
3. Route CLI capture and resume through `capture_pages`.
4. Route replay by stored run type.
5. Correct the live session class.
6. Keep fixture workflows working.
7. Run local real-Playwright integration without patching `_capture_selected`.
8. Keep private raw captures and session material outside Git.

## Execution waves

### Wave 0 — baseline and planning receipt

- Inspect the current diff.
- Run the existing quality gates.
- Confirm the 99-test baseline.
- Confirm Chromium is installed.
- Start the three Luna high agents with bounded assignments.

### Wave 1 — Phase 4A through 4C

- Agent A completes preflight and session health.
- Agent B completes the Playwright capture contract.
- Agent C completes extraction, discovery, and replay foundations.
- Root verifies each lane.
- Root integrates CLI, configuration, live workflow, and shared behavior.

### Wave 2 — local browser vertical slice

Use a local dynamic site to exercise real Playwright:

- navigation
- authentication-state classification
- discovery
- expansion
- scrolling
- raw-first storage
- interruption
- resume
- offline replay
- exports

Do not patch the capture function.

### Wave 3 — controlled one-Group run

Use an existing encrypted ready session when available.

Run:

1. direct URL workflow
2. guided or imported session workflow
3. live discovery workflow
4. intentional interruption
5. resume
6. offline replay
7. CSV, JSON, standalone SQLite, manifest, and Markdown export

Record only redacted receipts and non-private hashes.

If interactive login or a Group URL is the only remaining dependency, finish every non-interactive gate first.
Then request exactly that one input.
Do not claim the controlled gate passed before evidence exists.

### Wave 4 — controlled ten-Group run

Start only after the one-Group gate passes.

- Use the accepted one-Group workflow unchanged.
- Run sequentially first.
- Preserve completed Groups.
- Resume incomplete Groups.
- Measure duration, retries, CPU, memory, storage, completeness, and throughput.
- Test another worker limit only after the sequential baseline exists.

## Required acceptance gates

### One Group

- Both session methods reach ready.
- Live discovery or direct fallback selects one Group.
- Posts respect the 30-day boundary.
- Every visible top-level Comment is accounted for.
- Raw storage precedes extraction.
- Checkpoints precede browser interactions.
- Interrupted and uninterrupted identifiers match.
- Offline replay matches the completed run.
- Every output contains matching identifiers.
- Unsupported layouts produce zero false successes.
- Session secrets in Git, fixtures, logs, reports, and exports equal zero.

### Quality

- Identifier precision: 100%
- Supported required-field accuracy: at least 99%
- Pagination completeness: at least 99.5%
- Duplicate canonical records: at most 0.1%
- Test coverage: at least 80%

### Ten Groups

- All Groups reach explicit terminal states.
- Failures remain isolated.
- Completed Groups remain preserved.
- Resume matches uninterrupted results.
- Metrics explain the worker decision.

## Required verification

Run after every root integration:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
uv run detect-secrets scan --all-files
```

Also run:

```powershell
uv run pgscan doctor
uv run pgscan --help
uv run pgscan run --fixture tests/fixtures/one_group_capture.json --output OUTPUT --raw-root RAW_ROOT
uv run pgscan replay RUN_ID --offline --output OUTPUT --raw-root RAW_ROOT
```

Run the new local-browser and controlled operator commands defined during implementation.

## Completion receipts

Maintain:

- `docs/phase-4/phase-4-log.md`
- `docs/phase-4/phase-4-completion-report.md`
- `SESSION_STATE.md`
- `README.md`

Record:

- exact commands
- test count and coverage
- package, Python, Playwright, and Chromium versions
- session-health results without secrets
- run, interruption, resume, replay, normalized, and export hashes
- counts and completeness measurements
- Luna agent assignments and verified handbacks
- remaining limits
- exact integration commits
- final Git status

Create one root integration commit for each passed Phase 4 milestone.
Do not push unless the user explicitly requests it.

Finish with:

- the working operator command
- one-Group and ten-Group gate results
- exact hashes and metrics
- integration commit list
- clean Git status
- one short list of remaining limits

---
