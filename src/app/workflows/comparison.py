"""Direct Phase 3 comparison of two frozen CSV or JSON fixture result files."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class ComparisonInputMetrics:
    """Measured values derived from one immutable input file."""

    tool: str
    sha256: str
    expected_identifiers: int
    observed_identifiers: int
    identifier_completeness: float
    required_field_completeness: float
    duplicate_count: int
    duplicate_rate: float
    duration_seconds: float
    throughput_records_per_minute: float
    cost: float
    unsupported_fields: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return one traceable receipt entry."""
        return {
            "cost": self.cost,
            "duplicate_count": self.duplicate_count,
            "duplicate_rate": self.duplicate_rate,
            "duration_seconds": self.duration_seconds,
            "expected_identifiers": self.expected_identifiers,
            "identifier_completeness": self.identifier_completeness,
            "input_sha256": self.sha256,
            "observed_identifiers": self.observed_identifiers,
            "required_field_completeness": self.required_field_completeness,
            "throughput_records_per_minute": self.throughput_records_per_minute,
            "tool": self.tool,
            "unsupported_fields": list(self.unsupported_fields),
        }


@dataclass(frozen=True)
class ComparisonResult:
    """One Markdown report and its hash receipt."""

    inputs: dict[str, ComparisonInputMetrics]
    report_path: Path
    receipt_path: Path
    report_sha256: str

    def as_dict(self) -> dict[str, object]:
        """Return the operator-visible comparison result."""
        return {
            "report": str(self.report_path),
            "report_sha256": self.report_sha256,
            "receipt": str(self.receipt_path),
            "tools": sorted(self.inputs),
        }


@dataclass(frozen=True)
class _ResultRecord:
    """One expected identifier and its observed field coverage."""

    identifier: str
    expected: bool
    observed: bool
    expected_required_fields: int
    observed_required_fields: int
    unsupported_fields: tuple[str, ...]


@dataclass(frozen=True)
class _LoadedInput:
    """Parsed direct fixture input before metric calculation."""

    tool: str
    sha256: str
    duration_seconds: float
    cost: float
    records: tuple[_ResultRecord, ...]


class FixtureComparisonWorkflow:
    """Compare two direct result files without adapters or persistent tables."""

    def __init__(self, output: Path) -> None:
        self.output = output.resolve()
        self.report_path = self.output / "comparison-report.md"
        self.receipt_path = self.output / "comparison-receipt.json"

    def compare(self, first: Path, second: Path) -> ComparisonResult:
        """Calculate traceable metrics and separate measurements from conclusions."""
        loaded = (self._load(first), self._load(second))
        if loaded[0].tool == loaded[1].tool:
            raise ValueError("comparison tool labels must be distinct")
        expected_sets = [
            {record.identifier for record in value.records if record.expected} for value in loaded
        ]
        if expected_sets[0] != expected_sets[1]:
            raise ValueError("comparison inputs must use the same expected identifier workload")
        metrics = {value.tool: self._metrics(value) for value in loaded}
        report = self._report(metrics)
        self.output.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(report, encoding="utf-8")
        report_sha256 = sha256(self.report_path.read_bytes()).hexdigest()
        receipt = {
            "input_sha256": {tool: value.sha256 for tool, value in metrics.items()},
            "metrics": {tool: value.as_dict() for tool, value in metrics.items()},
            "report": self.report_path.name,
            "report_sha256": report_sha256,
            "schema_version": "1.0",
        }
        self.receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        return ComparisonResult(metrics, self.report_path, self.receipt_path, report_sha256)

    def _load(self, path: Path) -> _LoadedInput:
        source = path.resolve()
        raw = source.read_bytes()
        digest = sha256(raw).hexdigest()
        if source.suffix.lower() == ".json":
            return self._load_json(raw, digest)
        if source.suffix.lower() == ".csv":
            return self._load_csv(source, digest)
        raise ValueError("comparison inputs must be CSV or JSON")

    def _load_json(self, raw: bytes, digest: str) -> _LoadedInput:
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("comparison JSON is invalid") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            raise ValueError("comparison JSON must contain a records array")
        records = tuple(self._record(value) for value in payload["records"])
        return _LoadedInput(
            tool=self._text(payload.get("tool"), "tool"),
            sha256=digest,
            duration_seconds=self._non_negative_float(
                payload.get("duration_seconds"), "duration_seconds", positive=True
            ),
            cost=self._non_negative_float(payload.get("cost"), "cost"),
            records=records,
        )

    def _load_csv(self, path: Path, digest: str) -> _LoadedInput:
        try:
            with path.open(newline="", encoding="utf-8-sig") as source:
                rows = list(csv.DictReader(source))
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            raise ValueError("comparison CSV is invalid") from error
        if not rows:
            raise ValueError("comparison CSV must contain result rows")
        tools = {self._text(row.get("tool"), "tool") for row in rows}
        durations = {
            self._non_negative_float(row.get("duration_seconds"), "duration_seconds", positive=True)
            for row in rows
        }
        costs = {self._non_negative_float(row.get("cost"), "cost") for row in rows}
        if len(tools) != 1 or len(durations) != 1 or len(costs) != 1:
            raise ValueError("comparison CSV metadata must be consistent")
        records = tuple(self._record(row) for row in rows)
        return _LoadedInput(
            tool=next(iter(tools)),
            sha256=digest,
            duration_seconds=next(iter(durations)),
            cost=next(iter(costs)),
            records=records,
        )

    def _record(self, value: object) -> _ResultRecord:
        if not isinstance(value, dict):
            raise ValueError("comparison record must be an object")
        expected_fields = self._non_negative_int(
            value.get("expected_required_fields"), "expected_required_fields"
        )
        observed_fields = self._non_negative_int(
            value.get("observed_required_fields"), "observed_required_fields"
        )
        if observed_fields > expected_fields:
            raise ValueError("observed required fields exceed expected required fields")
        unsupported = value.get("unsupported_fields", ())
        if isinstance(unsupported, str):
            unsupported_values = tuple(
                sorted({item.strip() for item in unsupported.split("|") if item.strip()})
            )
        elif isinstance(unsupported, list):
            unsupported_values = tuple(
                sorted({self._text(item, "unsupported field") for item in unsupported})
            )
        else:
            raise ValueError("unsupported_fields must be an array or pipe-separated string")
        return _ResultRecord(
            identifier=self._text(value.get("identifier"), "identifier"),
            expected=self._boolean(value.get("expected"), "expected"),
            observed=self._boolean(value.get("observed"), "observed"),
            expected_required_fields=expected_fields,
            observed_required_fields=observed_fields,
            unsupported_fields=unsupported_values,
        )

    @staticmethod
    def _metrics(value: _LoadedInput) -> ComparisonInputMetrics:
        expected = {record.identifier for record in value.records if record.expected}
        observed_values = [record.identifier for record in value.records if record.observed]
        observed = set(observed_values)
        if not expected:
            raise ValueError("comparison input has no expected identifiers")
        duplicate_count = len(observed_values) - len(observed)
        unique_records: dict[str, _ResultRecord] = {}
        for record in value.records:
            if record.expected:
                unique_records.setdefault(record.identifier, record)
        expected_fields = sum(record.expected_required_fields for record in unique_records.values())
        if expected_fields <= 0:
            raise ValueError("comparison input has no expected required fields")
        observed_fields = sum(
            record.observed_required_fields if record.observed else 0
            for record in unique_records.values()
        )
        unsupported = tuple(
            sorted({field for record in value.records for field in record.unsupported_fields})
        )
        return ComparisonInputMetrics(
            tool=value.tool,
            sha256=value.sha256,
            expected_identifiers=len(expected),
            observed_identifiers=len(observed & expected),
            identifier_completeness=len(observed & expected) / len(expected),
            required_field_completeness=observed_fields / expected_fields,
            duplicate_count=duplicate_count,
            duplicate_rate=duplicate_count / len(observed_values) if observed_values else 0.0,
            duration_seconds=value.duration_seconds,
            throughput_records_per_minute=len(observed & expected) * 60 / value.duration_seconds,
            cost=value.cost,
            unsupported_fields=unsupported,
        )

    def _report(self, metrics: dict[str, ComparisonInputMetrics]) -> str:
        tools = sorted(metrics)
        header = (
            "| Tool | Input SHA-256 | Identifier completeness | Required-field completeness | "
            "Duplicates | Duplicate rate | Duration seconds | Throughput records/minute | Cost |"
        )
        separator = "|---|---|---:|---:|---:|---:|---:|---:|---:|"
        rows = [
            (
                f"| {tool} | `{metrics[tool].sha256}` | "
                f"{metrics[tool].identifier_completeness:.6f} | "
                f"{metrics[tool].required_field_completeness:.6f} | "
                f"{metrics[tool].duplicate_count} | {metrics[tool].duplicate_rate:.6f} | "
                f"{metrics[tool].duration_seconds:.6f} | "
                f"{metrics[tool].throughput_records_per_minute:.6f} | "
                f"{metrics[tool].cost:.6f} |"
            )
            for tool in tools
        ]
        lines = [
            "# Frozen fixture comparison",
            "",
            "## Measured values",
            "",
            header,
            separator,
            *rows,
            "",
            "## Unsupported fields",
            "",
        ]
        for tool in tools:
            fields = metrics[tool].unsupported_fields
            lines.append(f"- {tool}: {', '.join(fields) if fields else 'none'}")
        lines.extend(["", "## Conclusions", ""])
        criteria = (
            ("identifier completeness", "identifier_completeness", True),
            ("required-field completeness", "required_field_completeness", True),
            ("duplicate rate", "duplicate_rate", False),
            ("duration", "duration_seconds", False),
            ("throughput", "throughput_records_per_minute", True),
            ("cost", "cost", False),
        )
        for label, attribute, higher_is_better in criteria:
            values = {tool: float(getattr(metrics[tool], attribute)) for tool in tools}
            best = (max if higher_is_better else min)(values.values())
            leaders = sorted(tool for tool, measured in values.items() if measured == best)
            conclusion = "tie" if len(leaders) == len(tools) else ", ".join(leaders)
            lines.append(f"- {label}: {conclusion}")
        lines.extend(
            [
                "",
                "Conclusions use only the measured fixture values above.",
                "The report SHA-256 is stored in the adjacent comparison receipt.",
            ]
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _text(value: object, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _boolean(value: object, name: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ValueError(f"{name} must be true or false")

    @staticmethod
    def _non_negative_int(value: object, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError(f"{name} must be an integer")
        try:
            converted = int(value)
        except ValueError as error:
            raise ValueError(f"{name} must be an integer") from error
        if converted < 0:
            raise ValueError(f"{name} must be non-negative")
        return converted

    @staticmethod
    def _non_negative_float(value: object, name: str, *, positive: bool = False) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{name} must be numeric")
        try:
            converted = float(value)
        except ValueError as error:
            raise ValueError(f"{name} must be numeric") from error
        if converted < 0 or (positive and converted == 0):
            qualifier = "positive" if positive else "non-negative"
            raise ValueError(f"{name} must be {qualifier}")
        return converted
