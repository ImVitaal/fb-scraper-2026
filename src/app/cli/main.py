"""Command-line entry points for the local private-Group workflow."""

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from app import __version__
from app.capture.playwright_adapter import PlaywrightGroupCaptureAdapter
from app.configuration import (
    FixtureRunConfiguration,
    OperatorRunConfiguration,
    OperatorSessionConfiguration,
    OperatorTargetConfiguration,
)
from app.contracts.models import JobState
from app.discovery import SessionDiscoveryFixtureAdapter
from app.retention import RetentionService
from app.session import SessionProfileService, collect_guided_storage_state
from app.storage.database import Database
from app.storage.live_runs import LiveRunRepository
from app.storage.repositories import JobRepository
from app.targets import TargetPreparationService
from app.workflows import BatchFixtureWorkflow, FixtureWorkflow
from app.workflows.live_capture import LiveCaptureWorkflow

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
    with Database(configuration.output / "scanner.sqlite3") as database:
        database.migrate()
        sessions = SessionProfileService(database.connection, configuration.session_root)
        _prepare_session(sessions, configuration.session)
        state = sessions.read_state(configuration.session.profile)
        targets = TargetPreparationService(database.connection)
        selected = _prepare_target(targets, state, configuration.target)
    return _capture_selected(
        configuration.session.profile,
        selected.campaign_id,
        output=configuration.output,
        raw_root=configuration.raw_root,
        session_root=configuration.session_root,
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
):
    """Prepare and select exactly one configured Group."""
    if configuration.method == "url":
        assert configuration.url is not None
        return targets.add_url(configuration.url)
    if configuration.method == "csv":
        assert configuration.csv_file is not None
        campaign = targets.add_csv(configuration.csv_file)
    else:
        assert configuration.fixture is not None
        assert configuration.keyword is not None
        assert configuration.location is not None
        raw_html = SessionDiscoveryFixtureAdapter(state).capture(configuration.fixture)
        campaign = targets.add_discovery(
            raw_html,
            keyword=configuration.keyword,
            location=configuration.location,
        )
    assert configuration.select is not None
    candidate_id = _resolve_candidate(campaign.candidates, configuration.select)
    return targets.select(campaign.campaign_id, candidate_id)


def _resolve_candidate(candidates, selector: str) -> str:
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
    target_method = typer.prompt("Target method (discovery, url, csv)", default="discovery").strip()
    if target_method not in {"discovery", "url", "csv"}:
        raise ValueError("target method must be discovery, url, or csv")
    if target_method == "url":
        target = OperatorTargetConfiguration(method="url", url=typer.prompt("Group URL").strip())
    elif target_method == "csv":
        target = OperatorTargetConfiguration(
            method="csv",
            csv_file=Path(typer.prompt("CSV file")).expanduser().resolve(),
            select=typer.prompt("Select candidate by Group id or rank").strip(),
        )
    else:
        target = OperatorTargetConfiguration(
            method="discovery",
            fixture=Path(typer.prompt("Synthetic discovery capture")).expanduser().resolve(),
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
    )


def _capture_selected(
    profile: str,
    campaign: str,
    *,
    output: Path,
    raw_root: Path,
    session_root: Path,
) -> dict[str, object]:
    """Capture the selected Group through its encrypted browser session."""
    job_id = str(uuid4())
    with Database(output / "scanner.sqlite3") as database:
        database.migrate()
        sessions = SessionProfileService(database.connection, session_root)
        state = sessions.read_state(profile)
        selected = TargetPreparationService(database.connection).get_selected(campaign)
        JobRepository(database.connection).create(job_id)
        LiveRunRepository(database.connection).create(
            job_id,
            profile,
            selected,
            datetime.now(UTC) - timedelta(days=30),
            "playwright_group/1.0",
        )
    html = PlaywrightGroupCaptureAdapter(state).capture_group(selected.canonical_url)
    result = LiveCaptureWorkflow(output, raw_root).capture_html(job_id, html)
    return {
        "identifiers": list(result.identifiers),
        "job_id": result.job_id,
        "state": result.state.value,
    }


@app.command("capture")
def capture(
    profile: Annotated[str, typer.Option("--profile")],
    campaign: Annotated[str, typer.Option("--campaign")],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Capture the selected Group through its encrypted browser session."""
    try:
        result = _capture_selected(
            profile,
            campaign,
            output=output,
            raw_root=raw_root,
            session_root=session_root,
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
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(
        json.dumps(
            {
                "canonical_url": live.canonical_url,
                "group_id": live.group_id,
                "job_id": run_id,
                "lower_bound": live.lower_bound.isoformat(),
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
) -> None:
    """Resume one interrupted run."""
    try:
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            live = LiveRunRepository(database.connection).get(run_id)
            state = JobRepository(database.connection).get_state(run_id)
            if state not in {JobState.INTERRUPTED, JobState.PARTIAL}:
                raise ValueError("only interrupted or partial runs can resume")
            storage_state = SessionProfileService(database.connection, session_root).read_state(
                live.profile_id
            )
        html = PlaywrightGroupCaptureAdapter(storage_state).capture_group(live.canonical_url)
        result = LiveCaptureWorkflow(output, raw_root).capture_html(run_id, html)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(
        json.dumps(
            {
                "identifiers": list(result.identifiers),
                "job_id": result.job_id,
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
        result = FixtureWorkflow(output, raw_root).replay(run_id, offline=offline)
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


@session_app.command()
def login(
    profile: Annotated[str, typer.Option("--profile")],
    start_url: Annotated[str, typer.Option("--start-url")] = "https://www.facebook.com/",
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    session_root: Annotated[Path, typer.Option("--session-root")] = DEFAULT_SESSION_ROOT,
) -> None:
    """Prepare a session through a visible guided login."""
    try:
        state = collect_guided_storage_state(start_url)
        with Database(output / "scanner.sqlite3") as database:
            database.migrate()
            metadata = SessionProfileService(database.connection, session_root).save_guided_state(
                profile, state
            )
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(metadata.as_dict(), sort_keys=True))


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
