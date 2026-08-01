# Phase 4 one-shot Thread PM completion plan

**Date:** 2026-08-01

**Repository:** `C:\Users\teqhv\fb scraper`

**Branch:** `main`

**Objective:** turn the verified local release candidate into a proven operator release by fixing live discovery, passing one controlled Group, then passing ten Groups sequentially.

## Audited starting point

- `main` is pushed through `c57d29b` and matches `origin/main`.
- Ruff format, Ruff lint, and `ty` pass.
- Full suite: **217 passed**, **80.67% coverage**.
- `pgscan doctor`: **9/9 passed** on native Windows.
- Tracked-file secret scan: **0 findings**.
- Phases 1–3 are complete on synthetic/labelled fixtures.
- Phase 4A–4E and the Phase 4F protection controls are locally implemented.

## Review findings

| Priority | State | Finding | Completion evidence |
|---|---|---|---|
| P0 | Not working | The latest protected APP discovery capture stops with `unsupported_discovery_layout`; the live parser expects supported `main a[href*='/groups/']` candidate anchors that the current rendered layout did not expose. | A redacted regression fixture derived from the stored external capture parses joined candidates without weakening fail-closed behavior. |
| P0 | Not done | Phase 4F has no accepted APP one-Group receipt. The 30-day boundary, visible top-level Comment reconciliation, resume, replay, and export parity are proven locally, not against the controlled APP workflow. | Accepted receipts for the required session workflows plus matching run/resume/replay identifiers and all five exports. |
| P1 | Partly working | Normal-Chrome attach/finalize produced a ready encrypted session. Copied Chrome `Default` import remains incompatible with application-bound encryption, and the earlier Playwright-guided first login stalled at an account checkpoint. | One documented working guided preparation and one documented supported import preparation both reach `ready`; incompatible copied profiles keep their explicit diagnostic. |
| P1 | Not started | Phase 4G has no controlled ten-Group run. The existing `batch-run` command is synthetic, so live per-Group state, aggregate receipts, interruption, and incomplete-only resume are not demonstrated. | Ten sequential operator Groups reach explicit terminal states; injected interruption/recoverable failure resume without losing completed Groups. |
| P2 | Stale | Status documents disagree on 140/174/178/217 tests, whether the branch was pushed, and whether membership requests are part of the active contract. | One current phase log and completion report agree with Git and the final receipts. |
| Deferred | Intentionally unopened | Real competitor reruns and Phase 5 surface expansion depend on the Phase 4 exit gate. | Excluded from this plan. |

## Product decisions

1. Keep one worker and one Group interaction at a time.
2. Discover and select an **already joined, accessible** Group automatically; choose the lowest measured activity. Do not add membership actions to this release.
3. Treat the normal-Chrome attach/finalize path as the supported interactive preparation path. Keep supported storage-state import as the import path. Do not spend another cycle trying to decrypt application-bound Chrome profile data.
4. Repair only the layout actually observed, using the smallest redacted labelled fixture. Unknown layouts must still stop explicitly.
5. Extend the proven single-Group workflow for sequential live batching; do not design a new queue, scheduler, plugin system, or concurrency framework.
6. Keep all session data, private raw HTML, operator configs, and output outside Git.

## Thread PM operating contract

- Run the manager and every worker as **Luna with High reasoning**.
- Use independent Codex tasks, not subagents.
- At startup, inspect existing tasks and reuse one only when its goal and ownership still match.
- Give each task the bounded goal, owned paths, evidence, token forecast, and stop conditions below.
- Use event-driven `wait_threads` reviews at first artifact, blocker, failed test, stage gate, and completion.
- Root/manager owns prioritization, handoffs, acceptance, final synthesis, and the final commit/push; workers own substantive implementation in disjoint paths.
- Archive a worker task only after its useful result is integrated and independently checked.

### Compute brief

Relative RICE scores use Phase 4 completion reach, release impact, current evidence confidence, and expected effort.

| Task | RICE | Risk/value | Luna/High forecast | Rework + validation |
|---|---:|---|---:|---:|
| T1 — current-layout discovery | 100 | Release blocker / high | 25k–40k tokens | 12k included |
| T2 — controlled one-Group proof | 90 | Highest failure cost / high | 20k–35k tokens | 10k included |
| T3 — sequential ten-Group completion | 55 | Gate-dependent / high | 35k–55k tokens | 15k included |
| T4 — independent release verification | 45 | Consequential validation / medium | 15k–25k tokens | 8k included |
| Manager reserve and synthesis | — | Integration | 20k–30k tokens | 10k reserve |

**Total forecast:** 115k–185k tokens, medium-high relative consumption. No currency estimate is used without a reliable rate card. At 75% of a task budget, verify trajectory; at 90%, steer to evidence and closure. Increase scope only when a failed gate proves it necessary.

## One-shot execution

### Gate 0 — manager baseline

1. Confirm Luna/High and independent task-management tools are available.
2. Confirm `main == origin/main == c57d29b` and the worktree is clean.
3. Reuse the verified baseline above; do not rerun the four-minute suite until a code change exists.
4. Create T1 only. T2 waits for T1 acceptance; T3 waits for Phase 4F; T4 waits for the candidate release.

### T1 — make joined-Group discovery work on the observed layout

**Owned paths:** `src/app/discovery/`, a new uniquely named discovery fixture/test, and no shared CLI or migration files.

**Goal contract:**

1. Inspect the already-persisted external discovery raw capture locally without copying private content into Git or task messages.
2. Extract only the minimum structural anchors needed for Group ID/canonical URL, membership state, visible match evidence, and activity.
3. Create one fully synthetic/redacted labelled regression fixture representing that structure.
4. Write the failing test first.
5. Implement the smallest parser/capture adjustment that returns joined candidates and continues to reject Join/Requested candidates and unknown layouts.
6. Prove raw-first storage and `unsupported_discovery_layout` receipts still work.

**Acceptance:** focused tests pass; required identifiers are 100% correct on the labelled fixture; unsupported layout false-success count remains zero; Ruff and `ty` pass.

**Stop/reforecast:** if the capture contains no durable candidate identity, change only the discovery navigation/source to an authenticated joined-Groups view and preserve the same parser contract. Do not add OCR, GraphQL interception, or a general selector engine.

### T2 — pass the controlled one-Group gate

**Owned paths:** external operator roots and a uniquely named Phase 4F verification test if evidence exposes a defect. Shared source changes require a manager-approved narrow handoff.

**Goal contract:**

1. Run doctor and session health.
2. Prove the interactive attach/finalize session path and the supported import path both reach `ready` without secrets entering outputs or Git.
3. Run automatic keyword/location discovery and select the lowest-activity joined candidate.
4. Complete one visible, protected capture with the existing pacing, retry, stop, 30-Post, and one-active-capture limits.
5. Interrupt after a durable interaction, resume, then replay offline.
6. Compare Group/Post/Comment identifiers, 30-day filtering, visible top-level Comment reconciliation, CSV/JSON/SQLite/manifest/Markdown outputs, and receipt hashes.

**Acceptance:** every Phase 4F line in `OPERATOR_WORKING_RELEASE_PLAN.md` has a redacted evidence value; both session preparations complete; run/resume/replay and all exports agree; tracked secrets remain zero.

**Stop/reforecast:** stop immediately on session challenge/restriction, 401/403/429, or new layout drift. Fix only a reproduced product defect. Browser sign-in or checkpoint interaction is the only operator-visible pause.

### T3 — add and pass the minimal live ten-Group workflow

**Owned paths:** one new sequential operator-batch workflow, its unique tests, and its CLI/config integration. Reuse existing batch state/metric contracts where they fit.

**Goal contract:**

1. Accept the ten automatically selected joined Groups from the proven discovery contract.
2. Call the accepted one-Group operator workflow sequentially with worker limit fixed at one.
3. Persist per-Group terminal state before advancing, preserve completed Groups, and resume incomplete Groups only.
4. Enforce the existing 15-minute inter-Group pause and account stop circuit breakers.
5. Inject one interruption and one recoverable failure in labelled/local browser tests before the controlled run.
6. Produce one aggregate redacted receipt containing counts, retries, duration, CPU, memory, storage, completeness-adjusted throughput, and the retained worker-limit decision.

**Acceptance:** all ten Groups have explicit terminal states; successful Groups retain Phase 4F correctness; the resumed result matches the uninterrupted identifier set; no concurrency is introduced.

**Stop/reforecast:** a Phase 4F correctness regression closes 4G immediately and returns the defect to the smallest owning task. Do not compensate with retries, more workers, or new architecture.

### T4 — independent release verification

**Owned paths:** read-only review; it may add one isolated regression test only when a concrete missing assertion is demonstrated.

**Goal contract:** independently inspect the diff, final receipts, and phase gates; verify fixture evidence is not presented as APP evidence; run the complete local gate; check tracked secrets and Git cleanliness; report findings by severity.

**Commands:**

```powershell
uv run pgscan doctor
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
$files = @(git ls-files)
uv run detect-secrets scan @files
git diff --check
git status --short --branch
```

**Acceptance:** no P0/P1 finding remains; all commands pass; receipts satisfy Phase 4F and 4G; private data and session values in Git equal zero.

## Manager ship gate

1. Resolve worker contradictions from artifacts and tests, not status claims.
2. Update only `SESSION_STATE.md`, `docs/phase-4/phase-4-log.md`, and `docs/phase-4/phase-4-completion-report.md`; mark stale Phase 4 planning/status documents as superseded rather than adding another progress file.
3. Record current test count, coverage, doctor result, redacted receipt hashes, Phase 4F/4G gate results, and remaining limits.
4. Commit the integrated release, push `main`, confirm `main == origin/main`, then archive completed worker tasks.

## Definition of done

- Current live discovery selects an already joined accessible Group automatically.
- Interactive and supported import session preparations both complete the controlled one-Group workflow.
- One-Group capture, interruption, resume, offline replay, five exports, and Comment reconciliation agree.
- Ten Groups complete sequentially with isolated terminal states and incomplete-only resume.
- Full quality gates pass with at least 80% coverage and zero tracked secret findings.
- Phase 4 evidence is redacted, current, internally consistent, committed, and pushed.
- Competitor reruns and Phase 5 remain outside this release.
