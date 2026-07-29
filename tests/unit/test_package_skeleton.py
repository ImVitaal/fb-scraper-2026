from typer.testing import CliRunner

from app import __version__
from app.cli.main import app


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_lists_phase_one_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("run", "session", "inspect", "resume", "replay", "clean"):
        assert command in result.stdout


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "pgscan 0.1.0"
