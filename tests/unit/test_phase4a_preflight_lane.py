"""Phase 4A Windows preflight behavior tests."""

from __future__ import annotations

from pathlib import Path

from app.preflight import PreflightDependencies, run_preflight


def test_preflight_reports_every_required_check_without_root_values(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    roots = tuple(tmp_path / name for name in ("output-secret", "raw-secret", "session-secret"))
    dependencies = PreflightDependencies(
        platform_name=lambda: "Windows",
        python_version=lambda: (3, 12, 4),
        package_version=lambda: "0.1.0",
        migrations_ready=lambda: True,
        playwright_version=lambda: "1.55.0",
        chromium_executable=lambda: tmp_path / "chromium.exe",
        dpapi_round_trip=lambda value: value,
    )
    (tmp_path / "chromium.exe").write_bytes(b"fixture")

    report = run_preflight(repository, roots, dependencies=dependencies)

    assert report.ready is True
    assert {check.name for check in report.checks} == {
        "windows",
        "python",
        "package",
        "migrations",
        "playwright",
        "chromium",
        "dpapi",
        "writable_roots",
        "external_roots",
    }
    serialized = report.to_json()
    assert "output-secret" not in serialized
    assert "raw-secret" not in serialized
    assert "session-secret" not in serialized


def test_preflight_fails_closed_for_repository_roots_and_missing_chromium(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    dependencies = PreflightDependencies(
        platform_name=lambda: "Windows",
        python_version=lambda: (3, 12, 0),
        package_version=lambda: "0.1.0",
        migrations_ready=lambda: True,
        playwright_version=lambda: "1.55.0",
        chromium_executable=lambda: tmp_path / "missing.exe",
        dpapi_round_trip=lambda value: value,
    )

    report = run_preflight(
        repository,
        (repository / "output", tmp_path / "raw", tmp_path / "session"),
        dependencies=dependencies,
    )

    assert report.ready is False
    assert report.by_name("external_roots").passed is False
    assert report.by_name("chromium").passed is False
