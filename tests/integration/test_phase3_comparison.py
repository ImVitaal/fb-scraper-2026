"""Phase 3 direct fixture comparison acceptance tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli.main import app
from app.workflows.comparison import FixtureComparisonWorkflow

FIXTURES = Path(__file__).parents[1] / "fixtures" / "comparison"


def test_comparison_traces_metrics_to_input_and_output_hashes(tmp_path: Path) -> None:
    local = FIXTURES / "local-results.json"
    competitor = FIXTURES / "competitor-results.csv"

    result = FixtureComparisonWorkflow(tmp_path).compare(local, competitor)

    assert result.inputs["local-fixture"].sha256 == hashlib.sha256(local.read_bytes()).hexdigest()
    assert (
        result.inputs["competitor-fixture"].sha256
        == hashlib.sha256(competitor.read_bytes()).hexdigest()
    )
    assert result.inputs["local-fixture"].identifier_completeness == 1.0
    assert result.inputs["local-fixture"].duplicate_count == 0
    assert result.inputs["local-fixture"].cost == 0.0
    assert result.inputs["competitor-fixture"].identifier_completeness < 1.0
    assert result.inputs["competitor-fixture"].duplicate_count == 1
    assert "media.source_url" in result.inputs["competitor-fixture"].unsupported_fields
    assert result.report_sha256 == hashlib.sha256(result.report_path.read_bytes()).hexdigest()
    receipt = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert receipt["report_sha256"] == result.report_sha256
    assert receipt["input_sha256"]["local-fixture"] == result.inputs["local-fixture"].sha256


def test_report_separates_measured_values_from_conclusions(tmp_path: Path) -> None:
    result = FixtureComparisonWorkflow(tmp_path).compare(
        FIXTURES / "local-results.json",
        FIXTURES / "competitor-results.csv",
    )

    report = result.report_path.read_text(encoding="utf-8")
    assert "## Measured values" in report
    assert "## Conclusions" in report
    assert "## Unsupported fields" in report
    assert "local-fixture" in report
    assert "competitor-fixture" in report
    assert "Input SHA-256" in report
    assert "media.source_url" in report


def test_compare_cli_accepts_json_and_csv_without_adapters(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "compare",
            "--first",
            str(FIXTURES / "local-results.json"),
            "--second",
            str(FIXTURES / "competitor-results.csv"),
            "--output",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["report_sha256"]
    assert Path(payload["report"]).is_file()
    assert Path(payload["receipt"]).is_file()
    assert set(payload["tools"]) == {"local-fixture", "competitor-fixture"}
