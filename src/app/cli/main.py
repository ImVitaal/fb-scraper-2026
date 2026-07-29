"""Phase 1 command-line skeleton."""

from typing import Annotated

import typer

from app import __version__

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


@app.command()
def run() -> None:
    """Start the guided discovery-to-export workflow."""


@app.command()
def inspect(run_id: str) -> None:
    """Inspect one durable run."""


@app.command()
def resume(run_id: str) -> None:
    """Resume one interrupted run."""


@app.command()
def replay(run_id: str, offline: bool = True) -> None:
    """Replay stored raw captures."""


@app.command()
def clean(
    raw_older_than: str = "30d",
    normalized_older_than: str = "90d",
    dry_run: bool = True,
) -> None:
    """Apply configured retention periods."""


@session_app.command("import")
def import_session() -> None:
    """Import supported local browser session material."""


@session_app.command()
def login() -> None:
    """Prepare a session through a visible guided login."""


@session_app.command()
def inspect_session() -> None:
    """Inspect session metadata without revealing secrets."""


@session_app.command()
def delete() -> None:
    """Delete an encrypted session profile."""


def main() -> None:
    """Run the command-line application."""
    app()


if __name__ == "__main__":
    main()
