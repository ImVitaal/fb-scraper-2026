"""Command-line entry points for the local private-Group workflow."""

import json
import os
import random
import time
from collections.abc import Mapping
from contextlib import contextmanager, suppress
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Annotated, cast
from uuid import uuid4

import typer
from playwright.sync_api import StorageState as PlaywrightStorageState
from playwright.sync_api import sync_playwright

from app import __version__
from app.capture import BrowserCaptureLimits, BrowserStateError, GzipRawCaptureStore
from app.capture.playwright_adapter import PlaywrightGroupCaptureAdapter
from app.configuration import (
    FixtureRunConfiguration,
    OperatorProtectionConfiguration,
    OperatorRunConfiguration,
    OperatorSessionConfiguration,
    OperatorTargetConfiguration,
)
from app.contracts.models import JobState
from app.discovery import (
    DiscoveryMode,
    SessionDiscoveryAdapter,
    SessionDiscoveryFixtureAdapter,
)
from app.discovery.live import DiscoveryPage
from app.preflight import run_preflight
from app.retention import RetentionService
from app.session import (
    NormalChromeAttachmentFailure,
    NormalChromeAttachmentTimeout,
    SessionProfileService,
    collect_guided_storage_state,
    collect_imported_browser_profile_state,
    collect_normal_chrome_attachment_state,
    launch_normal_chrome_attachment,
    probe_with_playwright,
)
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository, RawCaptureMetadataRepository
from app.targets import TargetPreparationService
from app.workflows import BatchFixtureWorkflow, FixtureComparisonWorkflow, FixtureWorkflow
from app.workflows.html_replay import StoredHtmlReplayWorkflow
from app.workflows.live_capture import LiveCaptureWorkflow
from app.workflows.operator_receipt import OperatorRunReceiptWriter

app = typer.Typer(
    name="pgscan",
    help="Run the local private-Group collection workflow.",
    no_args_is_help=True,
)
session_app = typer.Typer(help="Prepare and manage encrypted session profiles.")
target_app = typer.Typer(help="Prepare one Group target through discovery or fallback inputs.")
app.add_typer(session_app, name="session")
app.add_typer(target_app, name="target")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pgscan {__version__}")
        raise typer.Exit


@app.callback()
def cli(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Run the local private-Group collection workflow."""


def _default_output() -> Path:
    """Return the per-user raw-data root, outside a source checkout."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "private-group-scanner"


DEFAULT_OUTPUT = _default_output()
DEFAULT_RAW_ROOT = DEFAULT_OUTPUT / "raw"
DEFAULT_SESSION_ROOT = DEFAULT_OUTPUT / "sessions"


@app.command()
def doctor(
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Check whether this Windows installation can run operator collection."""
    report = run_preflight(Path.cwd(), (output, raw_root, session_root))
    typer.echo(report.to_json())
    if not report.ready:
        raise typer.Exit(1)


@app.command()
def run(
    fixture: Annotated[
        Path | None, typer.Option("--fixture", dir_okay=False, readable=True)
    ] = None,
    config: Annotated[Path | None, typer.Option("--config", dir_okay=False, readable=True)] = None,
    guided: Annotated[bool, typer.Option("--guided")] = False,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Run a fixture or one connected operator workflow."""
    try:
        selected_modes = sum((fixture is not None, config is not None, guided))
        if selected_modes != 1:
            raise ValueError("use exactly one of --fixture, --config, or --guided")
        if guided:
            configured_operator = _guided_operator_configuration(
                output=output,
                raw_root=raw_root,
                session_root=session_root,
            )
            result = _run_operator(configured_operator)
        elif config is not None and OperatorRunConfiguration.is_operator(config):
            result = _run_operator(OperatorRunConfiguration.load(config))
        elif config is not None:
            configured = FixtureRunConfiguration.load(config)
            result = FixtureWorkflow(configured.output, configured.raw_root).run(configured.fixture)
        else:
            assert fixture is not None
            result = FixtureWorkflow(output, raw_root).run(fixture)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    payload = result if isinstance(result, dict) else result.as_dict()
    typer.echo(json.dumps(payload, sort_keys=True))


def _run_operator(configuration: OperatorRunConfiguration) -> dict[str, object]:
    """Prepare one session and target, then run the existing capture workflow."""
    discovery_protection: dict[str, object] = {}
    with Database(configuration.output / "scanner.sqlite3") as database:
        database.migrate()
        sessions = SessionProfileService(database.connection, configuration.session_root)
        _prepare_session(sessions, configuration.session)
        state = sessions.read_state(configuration.session.profile)
        health = sessions.probe_health(
            configuration.session.profile,
            configuration.session.start_url,
            probe_with_playwright,
        )
        if health.health.value != "ready":
            raise ValueError(f"session health is {health.health.value}")
        targets = TargetPreparationService(database.connection)
        try:
            selected = _prepare_target(
                targets,
                state,
                configuration.target,
                raw_root=configuration.raw_root,
                raw_captures=RawCaptureMetadataRepository(database.connection),
                protection=configuration.protection,
                protection_sink=discovery_protection,
            )
        except BrowserStateError as error:
            receipt = OperatorRunReceiptWriter(configuration.output).write_discovery_stop(
                str(uuid4()),
                profile=configuration.session.profile,
                protection=discovery_protection,
                stop_reason=error.failure_class,
            )
            raise BrowserStateError(
                error.failure_class,
                f"operator discovery stopped; receipt={receipt.path}",
            ) from error
    return _capture_selected(
        configuration.session.profile,
        selected.campaign_id,
        output=configuration.output,
        raw_root=configuration.raw_root,
        session_root=configuration.session_root,
        headless=configuration.headless,
        protection=configuration.protection,
        discovery_protection=discovery_protection,
    )


def _prepare_session(
    sessions: SessionProfileService,
    configuration: OperatorSessionConfiguration,
) -> None:
    """Prepare or validate the configured encrypted session profile."""
    if configuration.method == "existing":
        sessions.read_state(configuration.profile)
        return
    if configuration.method == "guided":
        state = collect_guided_storage_state(configuration.start_url)
        sessions.save_guided_state(configuration.profile, state)
        return
    assert configuration.state_file is not None
    try:
        state = json.loads(configuration.state_file.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError("imported session state could not be read") from error
    except json.JSONDecodeError as error:
        raise ValueError("imported session state is invalid JSON") from error
    sessions.import_state(configuration.profile, state)


def _prepare_target(
    targets: TargetPreparationService,
    state: Mapping[str, object],
    configuration: OperatorTargetConfiguration,
    *,
    raw_root: Path,
    raw_captures: RawCaptureMetadataRepository,
    protection: OperatorProtectionConfiguration | None = None,
    protection_sink: dict[str, object] | None = None,
):
    """Prepare and select exactly one configured Group."""
    if configuration.method == "url":
        assert configuration.url is not None
        return targets.add_url(configuration.url)
    if configuration.method == "csv":
        assert configuration.csv_file is not None
        campaign = targets.add_csv(configuration.csv_file)
    elif configuration.method == "discovery":
        assert configuration.fixture is not None
        assert configuration.keyword is not None
        assert configuration.location is not None
        raw_html = SessionDiscoveryFixtureAdapter(state).capture(configuration.fixture)
        campaign = targets.add_discovery(
            raw_html,
            keyword=configuration.keyword,
            location=configuration.location,
        )
    else:
        assert configuration.base_url is not None
        assert configuration.keyword is not None
        assert configuration.location is not None
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(storage_state=configuration_state(state))
                try:
                    page = context.new_page()
                    discovery_adapter = SessionDiscoveryAdapter(
                        mode=DiscoveryMode.LIVE,
                        base_url=configuration.base_url,
                        navigation_delay_seconds=(
                            random.uniform(*protection.navigation_delay_seconds)
                            if protection is not None
                            else 0.0
                        ),
                        retry_delays_seconds=(
                            protection.retry_delays_seconds if protection is not None else ()
                        ),
                        max_retries=2 if protection is not None else 0,
                    )
                    try:
                        captured = discovery_adapter.capture(
                            keyword=configuration.keyword,
                            location=configuration.location,
                            page=cast(DiscoveryPage, page),
                        )
                    finally:
                        if protection_sink is not None:
                            protection_sink.update(discovery_adapter.protection_telemetry)
                finally:
                    context.close()
            finally:
                browser.close()
        capture_id = sha256(captured.raw_html).hexdigest()
        stored = GzipRawCaptureStore(raw_root).write(
            capture_id,
            captured.raw_html,
            suffix=".discovery.html",
        )
        raw_captures.add(
            capture_id=capture_id,
            sha256=stored.sha256,
            source_url=captured.source_url,
            collected_at=datetime.now(UTC),
            storage_path=stored.path.name,
            byte_count=stored.byte_count,
        )
        campaign = targets.add_live_discovery(
            captured.raw_html,
            keyword=configuration.keyword,
            location=configuration.location,
            source_url=captured.source_url,
            raw_capture_id=capture_id,
        )
    assert configuration.select is not None
    candidate_id = _resolve_candidate(campaign.candidates, configuration.select)
    return targets.select(campaign.campaign_id, candidate_id)


def configuration_state(state: Mapping[str, object]) -> PlaywrightStorageState:
    """Cast validated encrypted profile state at the Playwright boundary."""
    return cast(PlaywrightStorageState, dict(state))


def _resolve_candidate(candidates, selector: str) -> str:
    if selector == "lowest-volume":
        measured = [
            candidate for candidate in candidates if candidate.activity_posts_per_day is not None
        ]
        if not measured:
            raise ValueError("automatic selection requires visible posts-per-day activity")
        return min(
            measured,
            key=lambda candidate: (
                candidate.activity_posts_per_day,
                candidate.rank,
                candidate.group_id,
            ),
        ).candidate_id
    matches = [
        candidate
        for candidate in candidates
        if selector in {candidate.candidate_id, candidate.group_id, str(candidate.rank)}
    ]
    if len(matches) != 1:
        raise ValueError("target selection must match exactly one candidate id, Group id, or rank")
    return matches[0].candidate_id


def _guided_operator_configuration(
    *,
    output: Path,
    raw_root: Path,
    session_root: Path,
) -> OperatorRunConfiguration:
    """Prompt for one operator workflow without echoing session material."""
    session_method = typer.prompt(
        "Session method (existing, imported, guided)", default="existing"
    ).strip()
    if session_method not in {"existing", "imported", "guided"}:
        raise ValueError("session method must be existing, imported, or guided")
    profile = typer.prompt("Session profile").strip()
    state_file = (
        Path(typer.prompt("Imported state file", hide_input=True)).expanduser().resolve()
        if session_method == "imported"
        else None
    )
    start_url = (
        typer.prompt("Guided login start URL", default="https://www.facebook.com/").strip()
        if session_method == "guided"
        else "https://www.facebook.com/"
    )
    target_method = typer.prompt(
        "Target method (live_discovery, discovery, url, csv)",
        default="live_discovery",
    ).strip()
    if target_method not in {"live_discovery", "discovery", "url", "csv"}:
        raise ValueError("target method must be live_discovery, discovery, url, or csv")
    if target_method == "url":
        target = OperatorTargetConfiguration(method="url", url=typer.prompt("Group URL").strip())
    elif target_method == "csv":
        target = OperatorTargetConfiguration(
            method="csv",
            csv_file=Path(typer.prompt("CSV file")).expanduser().resolve(),
            select=typer.prompt("Select candidate by Group id or rank").strip(),
        )
    elif target_method == "discovery":
        target = OperatorTargetConfiguration(
            method="discovery",
            fixture=Path(typer.prompt("Fixture discovery capture")).expanduser().resolve(),
            keyword=typer.prompt("Keyword").strip(),
            location=typer.prompt("Location").strip(),
            select=typer.prompt("Select candidate by Group id or rank").strip(),
        )
    else:
        target = OperatorTargetConfiguration(
            method="live_discovery",
            base_url=typer.prompt("APP base URL", default="https://www.facebook.com").strip(),
            keyword=typer.prompt("Keyword").strip(),
            location=typer.prompt("Location").strip(),
            select=typer.prompt("Select candidate by Group id or rank").strip(),
        )
    return OperatorRunConfiguration(
        output=output,
        raw_root=raw_root,
        session_root=session_root,
        session=OperatorSessionConfiguration(
            method=session_method,
            profile=profile,
            state_file=state_file,
            start_url=start_url,
        ),
        target=target,
        headless=False,
    )


def _protection_limits(
    protection: OperatorProtectionConfiguration,
) -> BrowserCaptureLimits:
    """Select one bounded delay from each configured release range."""
    return BrowserCaptureLimits(
        max_seconds=3600.0,
        max_retries=2,
        navigation_delay_seconds=random.uniform(*protection.navigation_delay_seconds),
        scroll_delay_seconds=random.uniform(*protection.scroll_delay_seconds),
        expansion_delay_seconds=random.uniform(*protection.expansion_delay_seconds),
        retry_delays_seconds=protection.retry_delays_seconds,
        max_recent_posts=protection.first_group_post_limit,
    )


def _protection_receipt(
    adapter: PlaywrightGroupCaptureAdapter,
    protection: OperatorProtectionConfiguration | None,
    *,
    between_group_wait_seconds: float = 0.0,
    discovery_protection: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Combine runtime telemetry with non-private operator limits."""
    payload = adapter.protection_telemetry
    if protection is None:
        return payload
    return payload | {
        "active_groups": protection.active_groups,
        "between_group_wait_applied_seconds": between_group_wait_seconds,
        "between_groups_seconds": protection.between_groups_seconds,
        "discovery": dict(discovery_protection or {}),
        "first_group_post_limit": protection.first_group_post_limit,
        "workers": protection.workers,
    }


@contextmanager
def _operator_capture_gate(
    output: Path,
    group_id: str,
    protection: OperatorProtectionConfiguration | None,
):
    """Enforce one operator capture and the configured inter-Group pause."""
    if protection is None:
        yield 0.0
        return
    output.mkdir(parents=True, exist_ok=True)
    lock_path = output / ".operator-capture.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("another operator Group capture is active") from error
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        waited = _wait_between_groups(output, group_id, protection.between_groups_seconds)
        yield waited
    finally:
        with suppress(OSError):
            os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _wait_between_groups(output: Path, group_id: str, minimum_seconds: float) -> float:
    """Wait after the latest successful capture of a different Group."""
    database_path = output / "scanner.sqlite3"
    if not database_path.exists():
        return 0.0
    with Database(database_path) as database:
        database.migrate()
        row = database.connection.execute(
            """
            SELECT jobs.updated_at
            FROM jobs
            JOIN live_runs ON live_runs.job_id = jobs.job_id
            WHERE jobs.state = 'succeeded' AND live_runs.group_id <> ?
            ORDER BY jobs.updated_at DESC
            LIMIT 1
            """,
            (group_id,),
        ).fetchone()
    if row is None:
        return 0.0
    elapsed = (datetime.now(UTC) - datetime.fromisoformat(str(row["updated_at"]))).total_seconds()
    remaining = max(0.0, minimum_seconds - elapsed)
    if remaining:
        time.sleep(remaining)
    return remaining


def _capture_selected(
    profile: str,
    campaign: str,
    *,
    output: Path,
    raw_root: Path,
    session_root: Path,
    headless: bool = False,
    protection: OperatorProtectionConfiguration | None = None,
    discovery_protection: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Capture the selected Group through its encrypted browser session."""
    job_id = str(uuid4())
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        selected = TargetPreparationService(database.connection).get_selected(campaign)
    with _operator_capture_gate(output, selected.group_id, protection) as between_group_wait:
        return _capture_selected_locked(
            job_id,
            profile,
            campaign,
            output=output,
            raw_root=raw_root,
            session_root=session_root,
            headless=headless,
            protection=protection,
            between_group_wait=between_group_wait,
            discovery_protection=discovery_protection,
        )


def _capture_selected_locked(
    job_id: str,
    profile: str,
    campaign: str,
    *,
    output: Path,
    raw_root: Path,
    session_root: Path,
    headless: bool,
    protection: OperatorProtectionConfiguration | None,
    between_group_wait: float,
    discovery_protection: Mapping[str, object] | None,
) -> dict[str, object]:
    """Run one selected capture while the exclusive operator gate is held."""
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        sessions = SessionProfileService(database.connection, session_root)
        state = sessions.read_state(profile)
        session_metadata = sessions.inspect(profile)
        browser_profile = (
            sessions.browser_profile_directory(profile)
            if session_metadata.source_browser.endswith("_persistent")
            else None
        )
        selected = TargetPreparationService(database.connection).get_selected(campaign)
        known_post_ids = {
            str(row["post_id"])
            for row in database.connection.execute(
                """
                SELECT DISTINCT post.post_id
                FROM posts AS post
                JOIN pagination_checkpoints AS checkpoint
                  ON checkpoint.raw_capture_id = post.raw_capture_id
                WHERE post.group_id = ?
                """,
                (selected.group_id,),
            )
        }
        JobRepository(database.connection).create(job_id)
        LiveRunRepository(database.connection).create(
            job_id,
            profile,
            selected,
            datetime.now(UTC) - timedelta(days=30),
            "app_rendered_html/1.0",
        )
    limits = _protection_limits(protection) if protection is not None else None
    adapter = PlaywrightGroupCaptureAdapter(
        state,
        headless=headless,
        limits=limits,
        known_post_ids=known_post_ids,
        user_data_directory=browser_profile,
        channel="chrome" if browser_profile is not None else None,
    )
    try:
        with adapter.capture_pages(
            selected.canonical_url,
            lower_bound=datetime.now(UTC) - timedelta(days=30),
        ) as capture_page:
            result = LiveCaptureWorkflow(output, raw_root).capture_pages(
                job_id,
                capture_page,
                max_pages=adapter.limits.max_pages,
            )
    except BrowserStateError as error:
        receipt = OperatorRunReceiptWriter(output).write_stop(
            job_id,
            adapter.limits,
            protection=_protection_receipt(
                adapter,
                protection,
                between_group_wait_seconds=between_group_wait,
                discovery_protection=discovery_protection,
            ),
            stop_reason=error.failure_class,
        )
        raise BrowserStateError(
            error.failure_class,
            f"operator stopped; receipt={receipt.path}",
        ) from error
    delivery = StoredHtmlReplayWorkflow(output, raw_root).replay(job_id, offline=True)
    receipt = OperatorRunReceiptWriter(output).write(
        job_id,
        delivery,
        adapter.limits,
        protection=_protection_receipt(
            adapter,
            protection,
            between_group_wait_seconds=between_group_wait,
            discovery_protection=discovery_protection,
        ),
    )
    return {
        "identifiers": list(result.identifiers),
        "job_id": result.job_id,
        "normalized_sha256": delivery.normalized_sha256,
        "receipt": str(receipt.path),
        "receipt_sha256": receipt.sha256,
        "state": result.state.value,
    }


@app.command("capture")
def capture(
    profile: Annotated[str, typer.Option("--profile")],
    campaign: Annotated[str, typer.Option("--campaign")],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
    headless: Annotated[bool, typer.Option("--headless")] = False,
) -> None:
    """Capture the selected Group through its encrypted browser session."""
    try:
        result = _capture_selected(
            profile,
            campaign,
            output=output,
            raw_root=raw_root,
            session_root=session_root,
            headless=headless,
            protection=OperatorProtectionConfiguration(),
        )
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result, sort_keys=True))


@app.command()
def inspect(
    run_id: str,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
) -> None:
    """Inspect one durable run."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            state = JobRepository(database.connection).get_state(run_id)
            live = LiveRunRepository(database.connection).get(run_id)
            page_row = database.connection.execute(
                """
                SELECT COUNT(*) AS pages, COALESCE(MAX(interaction_number), 0) AS interactions
                FROM pagination_checkpoints
                WHERE task_id = ?
                """,
                (run_id,),
            ).fetchone()
            counts = database.connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM groups WHERE group_id = ?) AS groups,
                    (SELECT COUNT(*) FROM posts WHERE group_id = ?) AS posts,
                    (SELECT COUNT(*) FROM comments WHERE group_id = ?) AS comments
                """,
                (live.group_id, live.group_id, live.group_id),
            ).fetchone()
            session = database.connection.execute(
                "SELECT health FROM session_profiles WHERE profile_id = ?",
                (live.profile_id,),
            ).fetchone()
            attempts = database.connection.execute(
                "SELECT COUNT(*) AS count FROM attempts WHERE task_id = ?",
                (run_id,),
            ).fetchone()
            failure = database.connection.execute(
                """
                SELECT failure_class
                FROM failures
                WHERE attempt_id IN (SELECT attempt_id FROM attempts WHERE task_id = ?)
                ORDER BY recorded_at DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(
        json.dumps(
            {
                "canonical_url": live.canonical_url,
                "group_id": live.group_id,
                "counts": {
                    "comments": int(counts["comments"]),
                    "groups": int(counts["groups"]),
                    "posts": int(counts["posts"]),
                },
                "failure_class": failure["failure_class"] if failure is not None else None,
                "interactions": int(page_row["interactions"]),
                "job_id": run_id,
                "lower_bound": live.lower_bound.isoformat(),
                "pages": int(page_row["pages"]),
                "retries": max(0, int(attempts["count"]) - 1),
                "session_health": session["health"] if session is not None else "session_invalid",
                "state": state.value,
            },
            sort_keys=True,
        )
    )


@app.command()
def resume(
    run_id: str,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
    headless: Annotated[bool, typer.Option("--headless")] = False,
) -> None:
    """Resume one interrupted run."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            live = LiveRunRepository(database.connection).get(run_id)
            state = JobRepository(database.connection).get_state(run_id)
            if state not in {JobState.INTERRUPTED, JobState.PARTIAL}:
                raise ValueError("only interrupted or partial runs can resume")
            sessions = SessionProfileService(database.connection, session_root)
            storage_state = sessions.read_state(live.profile_id)
            session_metadata = sessions.inspect(live.profile_id)
            browser_profile = (
                sessions.browser_profile_directory(live.profile_id)
                if session_metadata.source_browser.endswith("_persistent")
                else None
            )
        protection = OperatorProtectionConfiguration()
        adapter = PlaywrightGroupCaptureAdapter(
            storage_state,
            headless=headless,
            limits=_protection_limits(protection),
            user_data_directory=browser_profile,
            channel="chrome" if browser_profile is not None else None,
        )
        try:
            with adapter.capture_pages(
                live.canonical_url, lower_bound=live.lower_bound
            ) as capture_page:
                result = LiveCaptureWorkflow(output, raw_root).capture_pages(
                    run_id,
                    capture_page,
                    max_pages=adapter.limits.max_pages,
                )
        except BrowserStateError as error:
            receipt = OperatorRunReceiptWriter(output).write_stop(
                run_id,
                adapter.limits,
                protection=_protection_receipt(adapter, protection),
                stop_reason=error.failure_class,
            )
            raise BrowserStateError(
                error.failure_class,
                f"operator stopped; receipt={receipt.path}",
            ) from error
        delivery = StoredHtmlReplayWorkflow(output, raw_root).replay(run_id, offline=True)
        receipt = OperatorRunReceiptWriter(output).write(
            run_id,
            delivery,
            adapter.limits,
            protection=_protection_receipt(adapter, protection),
        )
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(
        json.dumps(
            {
                "identifiers": list(result.identifiers),
                "job_id": result.job_id,
                "normalized_sha256": delivery.normalized_sha256,
                "receipt": str(receipt.path),
                "receipt_sha256": receipt.sha256,
                "state": result.state.value,
            },
            sort_keys=True,
        )
    )


@app.command()
def replay(
    run_id: str,
    offline: Annotated[bool, typer.Option("--offline")] = True,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
) -> None:
    """Replay one stored raw capture without network access."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            live = database.connection.execute(
                "SELECT 1 FROM live_runs WHERE job_id = ?",
                (run_id,),
            ).fetchone()
        workflow = (
            StoredHtmlReplayWorkflow(output, raw_root)
            if live is not None
            else FixtureWorkflow(output, raw_root)
        )
        result = workflow.replay(run_id, offline=offline)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result.as_dict(), sort_keys=True))


@app.command("batch-run")
def batch_run(
    fixtures: Annotated[Path, typer.Option("--fixtures", file_okay=False, readable=True)],
    resume_batch: Annotated[bool, typer.Option("--resume")] = False,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
) -> None:
    """Run up to ten synthetic Groups with isolated terminal states."""
    try:
        result = BatchFixtureWorkflow(output, raw_root).run(fixtures, resume=resume_batch)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result.as_dict(), sort_keys=True))


@app.command("compare")
def compare(
    first: Annotated[Path, typer.Option("--first", dir_okay=False, readable=True)],
    second: Annotated[Path, typer.Option("--second", dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Compare two direct CSV or JSON fixture result files."""
    try:
        result = FixtureComparisonWorkflow(output).compare(first, second)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result.as_dict(), sort_keys=True))


@app.command()
def clean(
    raw_older_than: str = "30d",
    normalized_older_than: str = "90d",
    apply: Annotated[bool, typer.Option("--apply")] = False,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
) -> None:
    """Apply configured retention periods."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            receipts = RetentionService(database.connection, raw_root).clean(
                raw_older_than=raw_older_than,
                normalized_older_than=normalized_older_than,
                dry_run=not apply,
            )
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(
        json.dumps({"receipts": [receipt.as_dict() for receipt in receipts]}, sort_keys=True)
    )


@session_app.command("import")
def import_session(
    profile: Annotated[str, typer.Option("--profile")],
    state_file: Annotated[
        Path, typer.Option("--state-file", exists=True, dir_okay=False, readable=True)
    ],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Import supported local browser session material."""
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            metadata = SessionProfileService(database.connection, session_root).import_state(
                profile, state
            )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(metadata.as_dict(), sort_keys=True))


@session_app.command("import-browser")
def import_browser_session(
    profile: Annotated[str, typer.Option("--profile")],
    browser_profile: Annotated[
        Path,
        typer.Option("--browser-profile", exists=True, file_okay=False, readable=True),
    ],
    profile_name: Annotated[str, typer.Option("--profile-name")] = "Default",
    channel: Annotated[str | None, typer.Option("--channel")] = None,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Import one supported local Chromium profile into an encrypted envelope."""
    try:
        state = collect_imported_browser_profile_state(
            browser_profile,
            profile_name=profile_name,
            channel=channel,
        )
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            metadata = SessionProfileService(database.connection, session_root).import_state(
                profile,
                state,
                source_browser=f"{channel or 'chromium'}:{profile_name}",
            )
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(metadata.as_dict(), sort_keys=True))


@session_app.command()
def login(
    profile: Annotated[str, typer.Option("--profile")],
    start_url: Annotated[str, typer.Option("--start-url")] = "https://www.facebook.com/",
    channel: Annotated[str | None, typer.Option("--channel")] = "chrome",
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Prepare a session through a visible guided login in a selected browser channel."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            sessions = SessionProfileService(database.connection, session_root)
            browser_profile = sessions.browser_profile_directory(profile)
        state = collect_guided_storage_state(
            start_url,
            channel=channel,
            user_data_directory=browser_profile,
        )
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            metadata = SessionProfileService(database.connection, session_root).save_guided_state(
                profile,
                state,
                source_browser=f"playwright_{channel or 'chromium'}_persistent",
            )
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(metadata.as_dict(), sort_keys=True))


@session_app.command("attach-chrome")
def attach_chrome_session(
    profile: Annotated[str, typer.Option("--profile")],
    start_url: Annotated[str, typer.Option("--start-url")] = "https://www.facebook.com/",
    channel: Annotated[str | None, typer.Option("--channel")] = "chrome",
    attachment_timeout_seconds: Annotated[int, typer.Option("--attachment-timeout-seconds")] = 15,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Launch scanner-owned normal Chrome and wait for operator sign-in."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            browser_profile = SessionProfileService(
                database.connection, session_root
            ).browser_profile_directory(profile)
        launch_normal_chrome_attachment(
            start_url,
            user_data_directory=browser_profile,
            channel=channel,
            timeout_seconds=attachment_timeout_seconds,
        )
    except NormalChromeAttachmentTimeout:
        typer.echo(json.dumps({"state": "timeout"}, sort_keys=True))
        raise typer.Exit(1) from None
    except NormalChromeAttachmentFailure:
        typer.echo(json.dumps({"state": "attachment_failure"}, sort_keys=True))
        raise typer.Exit(1) from None
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps({"state": "awaiting_operator"}, sort_keys=True))


@session_app.command("finalize-chrome")
def finalize_chrome_session(
    profile: Annotated[str, typer.Option("--profile")],
    attachment_timeout_seconds: Annotated[int, typer.Option("--attachment-timeout-seconds")] = 15,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Encrypt the completed normal Chrome session and close its attachment."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            sessions = SessionProfileService(database.connection, session_root)
            state = collect_normal_chrome_attachment_state(
                user_data_directory=sessions.browser_profile_directory(profile),
                timeout_seconds=attachment_timeout_seconds,
            )
            metadata = sessions.save_guided_state(
                profile,
                state,
                source_browser="normal_chrome_cdp_persistent",
            )
    except NormalChromeAttachmentTimeout:
        typer.echo(json.dumps({"state": "timeout"}, sort_keys=True))
        raise typer.Exit(1) from None
    except NormalChromeAttachmentFailure:
        typer.echo(json.dumps({"state": "attachment_failure"}, sort_keys=True))
        raise typer.Exit(1) from None
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps({"metadata": metadata.as_dict(), "state": "completed"}, sort_keys=True))


@session_app.command("inspect")
def inspect_session(
    profile: Annotated[str, typer.Option("--profile")],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Inspect session metadata without revealing secrets."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            metadata = SessionProfileService(database.connection, session_root).inspect(profile)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(metadata.as_dict(), sort_keys=True))


@session_app.command("health")
def session_health(
    profile: Annotated[str, typer.Option("--profile")],
    probe_url: Annotated[str, typer.Option("--probe-url")],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Classify one encrypted session through an authenticated route."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            result = SessionProfileService(database.connection, session_root).probe_health(
                profile, probe_url, probe_with_playwright
            )
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result.as_dict(), sort_keys=True))
    if result.health.value != "ready":
        raise typer.Exit(1)


@session_app.command()
def delete(
    profile: Annotated[str, typer.Option("--profile")],
    yes: Annotated[bool, typer.Option("--yes")] = False,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Delete an encrypted session profile."""
    if not yes:
        typer.echo("error: pass --yes to delete a session profile")
        raise typer.Exit(1)
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            SessionProfileService(database.connection, session_root).delete(profile)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps({"deleted": profile}, sort_keys=True))


@target_app.command("add-url")
def add_url(
    url: Annotated[str, typer.Option("--url")],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
) -> None:
    """Create and select one direct Group URL fallback target."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            selected = TargetPreparationService(database.connection).add_url(url)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(selected.as_dict(), sort_keys=True))


@target_app.command("discover")
def discover_target(
    fixture: Annotated[Path, typer.Option("--fixture", exists=True, dir_okay=False, readable=True)],
    keyword: Annotated[str, typer.Option("--keyword")],
    location: Annotated[str, typer.Option("--location")],
    select: Annotated[str | None, typer.Option("--select")] = None,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
) -> None:
    """Create candidates from a captured keyword-and-location discovery result."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            service = TargetPreparationService(database.connection)
            campaign = service.add_discovery(
                fixture.read_bytes(), keyword=keyword, location=location
            )
            result = service.select(campaign.campaign_id, select) if select else campaign
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result.as_dict(), sort_keys=True))


@target_app.command("add-csv")
def add_csv(
    csv_file: Annotated[Path, typer.Option("--csv", exists=True, dir_okay=False, readable=True)],
    select: Annotated[str | None, typer.Option("--select")] = None,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
) -> None:
    """Create CSV fallback candidates and select exactly one candidate."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            service = TargetPreparationService(database.connection)
            campaign = service.add_csv(csv_file)
            result = service.select(campaign.campaign_id, select) if select else campaign
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result.as_dict(), sort_keys=True))


@target_app.command("select")
def select_target(
    campaign: Annotated[str, typer.Option("--campaign")],
    candidate: Annotated[str, typer.Option("--candidate")],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
) -> None:
    """Select one durable CSV or discovery candidate for a campaign."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            selected = TargetPreparationService(database.connection).select(campaign, candidate)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(selected.as_dict(), sort_keys=True))


def main() -> None:
    """Run the command-line application."""
    app()


if __name__ == "__main__":
    main()
