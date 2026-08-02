# Private Group Scanner — file map

**Location:** `C:\Users\teqhv\fb scraper\FILEMAP.md`
**Updated:** 2026-08-02
**Scope:** tracked project files. Private sessions, browser profiles, raw captures, exports, and receipts live outside Git and are intentionally omitted.

## Start here

| File | Purpose |
|---|---|
| `README.md` | Product overview and operator commands |
| `AGENTS.md` | Repository rules and quality gates |
| `LEAN_THREE_PHASE_COMPLETION_PLAN.md` | Current implementation direction |
| `SESSION_STATE.md` | Current release gates and external evidence |
| `docs/phase-4/phase-4-completion-report.md` | Phase 4 acceptance matrix |
| `docs/phase-4/PHASE_4_MANAGER_WRAP_UP_2026-08-02.md` | Latest manager handoff |
| `pyproject.toml` | Package, CLI, dependencies, and test configuration |
| `SECURITY.md` | Secret and private-data handling |

## Runtime flow

```text
CLI
└─ configuration / session preparation
   └─ discovery or URL/CSV target preparation
      └─ visible browser capture
         └─ raw storage before parsing
            └─ normalization / SQLite persistence
               └─ offline replay / exports / redacted receipts
```

## Repository tree

```text
.
├── .github/workflows/quality.yml                 CI quality checks
├── .gitignore
├── .python-version
├── AGENTS.md
├── CONTRIBUTING.md
├── FACEBOOK_PRODUCT_DISCOVERY_ANSWERS.md
├── FILEMAP.md                                    This file
├── LEAN_THREE_PHASE_COMPLETION_PLAN.md
├── README.md
├── SECURITY.md
├── SESSION_STATE.md
├── migrations/                                   Historical/root SQL migrations
│   ├── 001_initial.sql
│   ├── 002_integrity_guards.sql
│   ├── 003_session_metadata.sql
│   ├── 004_target_selection.sql
│   ├── 005_live_runs.sql
│   └── 006_membership_transitions.sql
├── docs/
│   ├── phase-1/
│   │   ├── phase-1-completion-report.md
│   │   └── phase-1-log.md
│   ├── phase-2/
│   │   ├── phase-2-completion-report.md
│   │   └── phase-2-log.md
│   ├── phase-3/
│   │   ├── phase-3-completion-report.md
│   │   └── phase-3-log.md
│   └── phase-4/
│       ├── PHASE_4_MANAGER_WRAP_UP_2026-08-02.md
│       ├── PHASE_4_ONE_SHOT_THREAD_PM_PLAN.md
│       ├── phase-4-completion-report.md
│       └── phase-4-log.md
├── src/app/
│   ├── __init__.py
│   ├── configuration.py                          Strict TOML configuration
│   ├── metrics.py                                Resource and throughput metrics
│   ├── preflight.py                              `pgscan doctor`
│   ├── protection_join.py                        Join pacing and one-action guard
│   ├── retention.py                              Retention and cleanup policy
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── pagination.py                         Pagination checkpoints
│   │   ├── playwright_adapter.py                 Visible browser capture adapter
│   │   ├── raw_store.py                           External raw capture storage
│   │   └── rendered.py                            Rendered-page capture contracts
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py                               All `pgscan` commands and orchestration
│   ├── contracts/
│   │   ├── __init__.py
│   │   └── models.py                             Versioned domain models and states
│   ├── discovery/
│   │   ├── __init__.py
│   │   ├── live.py                               APP discovery adapter/parser
│   │   ├── membership.py                          Membership state and join adapter
│   │   ├── parser.py                              Fixture discovery parser
│   │   └── session_fixture.py                     Session-backed fixture adapter
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── app_group.py                           APP Group/Post/Comment extraction
│   │   ├── fixture.py                             Fixture extraction
│   │   └── live_group.py                          Live rendered Group parsing
│   ├── session/
│   │   ├── __init__.py
│   │   ├── browser.py                             Guided/imported/Chrome attachment
│   │   ├── dpapi.py                               Windows user-bound encryption
│   │   ├── health.py                              Session health classification
│   │   └── profiles.py                            Encrypted session envelopes
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py                            SQLite connection and migrations
│   │   ├── live_runs.py                           Live-run persistence
│   │   ├── repositories.py                        Jobs/raw metadata/checkpoints
│   │   └── migrations/
│   │       ├── 001_initial.sql
│   │       ├── 002_integrity_guards.sql
│   │       ├── 003_session_metadata.sql
│   │       ├── 004_target_selection.sql
│   │       ├── 005_live_runs.sql
│   │       └── 006_membership_transitions.sql
│   ├── targets/
│   │   ├── __init__.py
│   │   └── preparation.py                         URL/CSV/discovery campaigns
│   └── workflows/
│       ├── __init__.py
│       ├── batch_run.py                            Synthetic batch workflow
│       ├── comparison.py                           Competitor comparison workflow
│       ├── fixture_run.py                          Fixture capture/replay workflow
│       ├── html_replay.py                          Offline raw replay
│       ├── live_capture.py                         Live capture and normalization
│       ├── operator_batch.py                       Phase 4G sequential operator batch
│       └── operator_receipt.py                     Redacted operator receipts/exports
├── tests/
│   ├── fixtures/
│   │   ├── app_operator_redacted/                 Synthetic APP-shaped HTML
│   │   │   ├── discovery.html
│   │   │   ├── group_page.html
│   │   │   └── t1_current_rendered_discovery.html
│   │   ├── comparison/
│   │   │   ├── competitor-results.csv
│   │   │   └── local-results.json
│   │   ├── live_group_pages/group.html
│   │   ├── one_group_capture.json
│   │   ├── phase4b_browser/
│   │   │   ├── dynamic_group.html
│   │   │   └── failure.html
│   │   └── ten_groups/group-01.json … group-10.json
│   ├── integration/                              Vertical and lane tests
│   │   ├── test_capture_resume_lane.py
│   │   ├── test_fixture_replay.py
│   │   ├── test_keyword_join_receipt_contract.py
│   │   ├── test_live_capture.py
│   │   ├── test_normal_chrome_attachment_cli.py
│   │   ├── test_operator_toml_lane.py
│   │   ├── test_output_replay_retention_lane.py
│   │   ├── test_phase2_batch.py
│   │   ├── test_phase3_comparison.py
│   │   ├── test_phase4_root_local_browser_vertical.py
│   │   ├── test_phase4_root_preflight_cli.py
│   │   ├── test_phase4b_browser_contract.py
│   │   ├── test_phase4c_app_html_replay_lane.py
│   │   ├── test_phase4f_known_post_skipping_lane.py
│   │   ├── test_phase4f_local_parity_receipt.py
│   │   ├── test_phase4f_stop_receipt_lane.py
│   │   ├── test_phase4g_cli_adapter.py
│   │   ├── test_phase4g_operator_batch.py
│   │   ├── test_session_cli.py
│   │   └── test_storage.py
│   └── unit/                                     Contract and component tests
│       ├── test_configuration.py
│       ├── test_contracts.py
│       ├── test_discovery.py
│       ├── test_discovery_stop_join_receipt.py
│       ├── test_keyword_join_preparation.py
│       ├── test_live_group_parser.py
│       ├── test_live_runs.py
│       ├── test_measurement_receipts_lane.py
│       ├── test_membership_join_adapter.py
│       ├── test_membership_transition_preparation.py
│       ├── test_metrics.py
│       ├── test_normal_chrome_attachment.py
│       ├── test_operator_configuration_lane.py
│       ├── test_package_skeleton.py
│       ├── test_pagination.py
│       ├── test_phase4_persistent_discovery.py
│       ├── test_phase4_root_browser_import.py
│       ├── test_phase4_t1_joined_groups_navigation.py
│       ├── test_phase4a_preflight_lane.py
│       ├── test_phase4a_session_health_lane.py
│       ├── test_phase4c_app_extraction_lane.py
│       ├── test_phase4c_live_discovery_lane.py
│       ├── test_phase4f_browser_pacing_lane.py
│       ├── test_phase4f_empty_group_shell_guard.py
│       ├── test_phase4f_join_protection_lane.py
│       ├── test_phase4f_live_discovery_protection.py
│       ├── test_phase4f_operator_protection.py
│       ├── test_phase4f_operator_runtime.py
│       ├── test_rendered_capture_lane.py
│       ├── test_session_discovery_lane.py
│       ├── test_session_profiles.py
│       └── test_target_preparation.py
├── pyproject.toml                                 Build and quality configuration
└── uv.lock                                        Locked Python dependencies
```

## Data boundary

The operator runtime root is `%LOCALAPPDATA%\private-group-scanner`. Keep session envelopes, browser profiles, raw HTML, exports, and receipts there; commit only synthetic fixtures, redacted documentation, and source code.
