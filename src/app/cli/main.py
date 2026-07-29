"""Command-line entry points for the local private-Group workflow."""

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from app import __version__
from app.session import SessionProfileService, collect_guided_storage_state
from app.storage.database import Database
from app.workflows import FixtureWorkflow

app = typer.Typer(
    name="pgscan",
    help="Run the local private-Group collection workflow.",
    no_args_is_help=True,
)
session_app = typer.Typer(help="Prepare and manage encrypted session profiles.")
app.add_typer(session_app, name="session")


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
    fixture: Annotated[Path, typer.Option("--fixture", exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_OUTPUT,
    raw_root: Annotated[Path, typer.Option("--raw-root")] = DEFAULT_RAW_ROOT,
) -> None:
    """Store, parse, persist, and export one synthetic raw fixture."""
    try:
        result = FixtureWorkflow(output, raw_root).run(fixture)
    except (OSError, ValueError, RuntimeError) as error:
        typer.echo(f"error: {error}")
        raise typer.Exit(1) from error
    typer.echo(json.dumps(result.as_dict(), sort_keys=True))


@app.command()
def inspect(run_id: str) -> None:
    """Inspect one durable run."""


@app.command()
def resume(run_id: str) -> None:
    """Resume one interrupted run."""


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


@app.command()
def clean(
    raw_older_than: str = "30d",
    normalized_older_than: str = "90d",
    dry_run: bool = True,
) -> None:
    """Apply configured retention periods."""


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


def main() -> None:
    """Run the command-line application."""
    app()


if __name__ == "__main__":
    main()
