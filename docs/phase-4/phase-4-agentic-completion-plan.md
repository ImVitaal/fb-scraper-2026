# Phase 4 Agentic Completion Plan

## Objective

Finish one reliable keyword-driven Group workflow without broadening the product:

1. discover Groups from an authenticated session using keyword and location;
2. collect an already joined qualifying Group, or request membership for one qualifying Group when none is joined;
3. collect up to 30 recent posts and every visible top-level comment;
4. export CSV, JSON, SQLite, manifest, Markdown, and a redacted receipt;
5. replay offline and prove count, identifier, and hash parity.

Root owns the visible browser, all live actions, shared contracts, documentation, and commits. Private session material and raw captures stay outside Git.

## Critical review of the initial plan

| Finding | Why it matters | Improvement |
|---|---|---|
| The first plan treated the local-quality lane as a generic agent task. | The full suite had one known migration expectation failure, and its rerun was interrupted. | Root first commits the small repair, then runs the full gate once from a clean tree. Agents receive bounded audits only after that baseline exists. |
| The membership rule was implicit. | Joining unnecessarily wastes the single-action budget; ignoring a joinable result defeats keyword-driven acquisition. | Use a deterministic rule: collect one already-joined qualifying result when present; otherwise request membership for exactly one qualifying `join_available` result. Never act on `join_requested`, rejected, or previously attempted IDs. |
| Receipt and replay evidence were separate checklist items. | A green capture without linked discovery/confirmation raw hashes is weak evidence. | Treat transition evidence as one contract: discovery raw hash, confirmation raw hash, redacted transition telemetry, then offline integrity verification before replay. |
| Parallel work could overlap root-owned files. | Concurrent edits to CLI, migrations, and receipt code cause integration churn. | Agents are audit/test-only and use disjoint tests or written findings. Root applies shared-code changes. |
| The live run was scheduled before a complete local gate. | Runtime debugging while static failures remain creates noisy evidence. | Require Ruff, ty, full pytest, and secret scan before browser execution. |
| Completion criteria were not ordered for a pending membership request. | A request can be accepted but not grant immediate collection access. | A pending/rejected/stopped transition ends the live attempt with a redacted receipt; do not repeat the same action. A successful collection requires confirmed membership plus all export/replay gates. |

## Improved execution plan

### 0. Freeze and commit the local baseline — Root

- Inspect `git diff --check` and ensure only source/tests are staged.
- Commit the current migration-test and join-adapter coverage repair.
- Confirm `git status --short` is empty.

**Exit:** a named commit exists and Git is clean.

### 1. Local verification — Root with three bounded audit lanes

| Lane | Scope | Owned paths | Deliverable |
|---|---|---|---|
| A: quality | Run full Ruff, ty, pytest; isolate the first failure. | No shared-code edits. | Exact command output and one minimal-fix recommendation. |
| B: evidence | Check migration 006, transition receipt fields, transition raw integrity, replay and export parity tests. | New test only if required. | Pass/fail matrix with missing assertion, if any. |
| C: readiness | Check configuration, encrypted session health, pacing ranges, one-action guard, and Join selector against existing browser contracts. | No browser action and no shared-code edits. | Go/no-go checklist. |

Root reviews findings and makes only focused changes. Then run:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
$tracked = @(git ls-files)
$scan = & uv run detect-secrets scan @tracked | ConvertFrom-Json
@($scan.results.PSObject.Properties).Count
```

**Exit:** all four commands pass; secret count is `0`.

### 2. Visible live workflow — Root only

Use the existing encrypted `operator` session and a local configuration outside the repository.

1. Run `pgscan doctor` and `pgscan session health`.
2. Start a visible browser.
3. Search exact configured keyword and location.
4. Persist discovery raw HTML before any membership action.
5. Apply the selection rule:
   - choose one already joined qualifying Group, otherwise
   - reserve and click one `join_available` Group after the configured 10–20 second pacing delay.
6. Persist a pre-click checkpoint, confirmation raw capture, and redacted transition telemetry.
7. Stop immediately on login, challenge, CAPTCHA, restriction, or HTTP 401/403/429.
8. For confirmed access, collect no more than 30 recent posts and all visible top-level comments using existing pacing, checkpoints, retries, cooldown, activity limit, and account-stop controls.

**Hard limits:** one worker, one active Group, one membership action, no comment replies, no social actions beyond the single membership request.

**Exit:** confirmed accessible Group capture completes, or a durable redacted stop receipt records the one attempted transition.

### 3. Evidence and release closeout — Root

For a completed capture:

1. Verify CSV, JSON, SQLite, manifest, Markdown, and operator receipt exist outside Git.
2. Run `pgscan replay JOB_ID --offline`.
3. Compare exported counts, canonical identifiers, manifest hashes, receipt hashes, and replay normalized hash.
4. Update the existing Phase 4 log, current status, and session state using redacted values only.
5. Re-run the complete local gate and secret scan after documentation changes.
6. Commit source/tests/docs; confirm a clean worktree.

## Completion definition

`WORKING PROTOTYPE PASSED` is emitted only when all of these are true:

- local quality and secret gates pass;
- one live Group workflow completed with documented pacing and stop controls;
- exports, receipt, and offline replay exist and agree on counts, identifiers, and hashes;
- Phase 4 records contain redacted evidence;
- Git is clean after the verified commit.
