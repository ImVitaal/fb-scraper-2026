# Private Group Scanner — Phase 4 operator working release plan

**Date:** 2026-07-29
**Status:** Current execution source after the Phases 1–3 fixture release
**Objective:** Complete one controlled APP Group workflow, then repeat it across ten Groups.

## Release decision

Do not start surface expansion.

The fixture release proves storage, contracts, resume rules, outputs, measurements, and comparison calculations.
It does not prove the complete operator workflow against APP.

Phase 4 must close the operator gap before Pages, Events, scheduling, intelligence, or other product expansion.

## Current review

| Milestone | Result | Evidence |
|---|---|---|
| 4A | Implemented and locally verified | `90a8a5b` |
| 4B | Implemented and locally verified | `ec3f3b1` |
| 4C | Implemented and locally verified | `5c15f56` |
| 4D–4E | Integrated and locally verified | `8568625`, `98c515a`, `9a6ec4f` |
| 4F | Local browser gates pass; controlled APP receipt pending | Phase 4 log |
| 4G | Not started | Requires accepted 4F receipt |

The operator browser is visible by default. `--headless` is an explicit automation option.
Browser-profile import copies the selected closed profile before launch and preserves its source.
Each completed operator run writes a stable receipt containing non-private hashes, counts, versions, metrics, and limits.

## Phase 4 rules

1. Keep one active milestone.
2. Start with one direct Group URL.
3. Use one controlled operator account and visible browser.
4. Store private raw captures outside Git.
5. Commit only synthetic or redacted labelled fixtures.
6. Store raw bytes before transformation or parsing.
7. Persist interaction checkpoints before the next browser action.
8. Treat challenge, restriction, login, and layout drift as non-success states.
9. Keep the sequential worker limit at one until measurements justify a change.
10. Do not restart competitor work before the operator gate passes.

## 4A — honest preflight and session health

### Operator-visible result

`pgscan doctor` reports whether this Windows installation can run a controlled collection.

### Implement

- Check Python, package, migrations, writable roots, DPAPI, Playwright, and Chromium.
- Check that output, raw, and session roots remain outside the repository.
- Navigate one lightweight authenticated APP route through the selected session.
- Classify session health as ready, expired, challenged, restricted, or invalid.
- Store only non-secret health evidence.
- Keep guided login and imported session workflows behind the same probe.
- Document the exact supported imported-session format.

### Gate

- `doctor` passes on the target Windows environment.
- Both session methods reach `ready`.
- Each injected session failure maps to one explicit non-success health state.
- No cookie, token, password, or storage-state value enters output or Git.

## 4B — real browser capture contract

### Operator-visible result

A direct Group URL produces durable raw captures through the selected encrypted session.

### Implement

- Replace the one-page adapter with a `RenderedPageCapture` implementation.
- Keep one Playwright context alive for the complete run.
- Wait for explicit content-ready or failure conditions.
- Detect login, challenge, restriction, unavailable Group, and layout drift pages.
- Expand visible posts and top-level comments.
- Scroll until the 30-day boundary and visible-comment completion conditions hold.
- Derive an opaque next-action checkpoint from the current interaction state.
- Persist that checkpoint before the next click, expansion, or scroll.
- Bound pages, interactions, retries, time, and storage.
- Close the browser context after success, failure, or interruption.

### Gate

- The CLI calls `capture_pages`, not `capture_html`.
- An intentional interruption resumes from the latest durable interaction.
- Resumed and uninterrupted raw-capture sets match.
- Page and interaction bounds produce explicit failures.

## 4C — APP extraction and versioned parsing

### Operator-visible result

Stored APP captures produce Group, Post, top-level Comment, and media metadata records.

### Implement

- Preserve the original rendered HTML before extraction.
- Add one versioned APP extraction adapter.
- Derive identifiers from canonical links or captured structured identifiers.
- Record source paths and structured null reasons.
- Keep replies excluded.
- Exclude Posts older than 30 days.
- Include every visible top-level Comment on included Posts.
- Store media type, source URL, and available alternative text.
- Keep the fixture parser unchanged for deterministic regression tests.
- Label operator records with the actual imported or guided session class.

### Evidence method

- Collect controlled private raw captures outside the repository.
- Create the smallest redacted labelled fixtures needed for tests.
- Remove names, text, cookies, tokens, and private URLs from committed fixtures.
- Record the redaction and labelling method in the Phase 4 log.

### Gate

- Identifier precision equals 100% on labelled operator-derived fixtures.
- Supported required-field accuracy reaches at least 99%.
- Pagination completeness reaches at least 99.5%.
- Duplicate canonical records remain at or below 0.1%.
- Unsupported layouts produce zero false successes.

## 4D — live discovery and target selection

### Operator-visible result

The active session discovers accessible Groups from a keyword and location.

### Implement

- Replace fixture discovery in operator mode with a Playwright discovery adapter.
- Store the raw discovery capture before parsing.
- Parse Group identifier, canonical URL, name, and matching evidence.
- Rank candidates deterministically.
- Let the operator select exactly one candidate.
- Keep direct URL and CSV as first-class fallback paths.
- Retain fixture discovery only as an explicit test mode.

### Gate

- Keyword and location return controlled accessible candidates.
- Selection persists exactly one Group.
- Direct URL, CSV, and discovery produce the same selected-target contract.
- Session or layout failures never produce a selected target.

## 4E — live replay, resume, export, and inspection

### Operator-visible result

`inspect`, `resume`, and `replay` work for one controlled operator run.

### Implement

- Route replay by stored run type.
- Use `StoredHtmlReplayWorkflow` for captured HTML runs.
- Reconnect resume to the multi-page Playwright adapter.
- Export CSV, JSON, standalone SQLite, manifest, and Markdown after live success.
- Show pages, interactions, counts, health, failure class, and retry count in `inspect`.
- Add a stable run receipt with input, raw, normalized, and export hashes.
- Keep cleanup dry-run by default.

### Gate

- Run, resume, and offline replay identifiers match.
- Every output contains the same identifiers.
- Replay performs no browser or network operation.
- Tampered or missing raw captures stop replay.
- Cleanup respects 30-day raw and 90-day normalized boundaries.

## 4F — controlled one-Group completion

### Required runs

1. Complete guided login, direct URL, capture, export, and replay.
2. Complete imported session, discovery, selection, capture, export, and replay.
3. Interrupt one run after a durable interaction.
4. Resume the interrupted run.
5. Replay the completed raw captures offline.

### Gate

- Both session methods complete.
- The 30-day boundary is correct.
- Every visible top-level Comment is accounted for.
- Run, resume, and replay identifiers match.
- All required outputs match.
- The completion receipt contains non-private hashes, counts, versions, timings, and limits.
- Session secrets in Git, fixtures, logs, reports, and exports equal zero.

## 4G — controlled ten-Group reliability

Start this milestone only after 4F passes.

### Implement

- Reuse the accepted one-Group operator workflow.
- Run ten selected Groups sequentially.
- Persist per-Group terminal states.
- Inject one interruption and one recoverable failure.
- Preserve completed Groups.
- Resume only incomplete Groups.
- Measure duration, retries, CPU, memory, storage, and completeness-adjusted throughput.
- Test another worker limit only after the sequential measurement exists.

### Gate

- All ten Groups reach explicit terminal states.
- Successful Groups retain the one-Group correctness rates.
- Failures remain isolated and actionable.
- Resume matches uninterrupted results.
- The report identifies the measured worker decision.

## Required test layers

### Unit

- Session-health classification.
- Browser-state classification.
- Interaction checkpoint generation.
- APP extraction and null reasons.
- Run-type replay routing.

### Local browser integration

- Serve synthetic dynamic pages locally.
- Exercise real Playwright navigation, expansion, scrolling, interruption, and resume.
- Do not patch `_capture_selected`.
- Confirm raw storage occurs before extraction.

### Controlled operator validation

- Use private captures outside Git.
- Record only redacted receipts and non-private hashes.
- Stop promotion when identifiers or completeness remain unlabelled.

## Ownership for later delegated execution

- Root owns contracts, migrations, CLI integration, phase logs, receipts, and commits.
- Session lane owns `src/app/session/`, doctor checks, and session-health tests.
- Browser lane owns `src/app/capture/`, Playwright interaction code, and browser tests.
- Extraction lane owns live discovery, live parsing, replay routing, and redacted fixtures.
- Lanes must use disjoint test filenames and must not edit another lane.

## Phase 4 exit

Phase 4 passes only when the controlled one-Group and ten-Group gates both pass.

After Phase 4:

- Re-run direct competitor measurements with real exports.
- Move product expansion to Phase 5.
- Select Phase 5 features from measured operator needs.

## Immediate next action

Complete 4F with one controlled session and target bundle.

```text
SESSION_METHOD=guided|browser_profile
PROFILE_NAME=Default|Profile 2|Profile 3
TARGET=GROUP_URL|KEYWORD+LOCATION
```

Close the source browser before profile import. Start 4G only after the 4F receipt passes.
