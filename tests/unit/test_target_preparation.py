"""Tests for direct URL and CSV private-Group target selection."""

from __future__ import annotations

import csv
from pathlib import Path

from app.storage.database import Database
from app.targets.preparation import TargetPreparationService


def test_direct_url_creates_one_selected_target(tmp_path: Path) -> None:
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        selected = TargetPreparationService(database.connection).add_url(
            "https://example.test/groups/group-1001?ref=search"
        )

    assert selected.source == "direct_url"
    assert selected.group_id == "group-1001"
    assert selected.canonical_url == "https://example.test/groups/group-1001"


def test_csv_requires_an_explicit_candidate_and_selects_one(tmp_path: Path) -> None:
    csv_path = tmp_path / "groups.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=["group_url", "name"])
        writer.writeheader()
        writer.writerows(
            [
                {"group_url": "https://example.test/groups/group-1", "name": "One"},
                {"group_url": "https://example.test/groups/group-2", "name": "Two"},
                {"group_url": "https://example.test/groups/group-1", "name": "Duplicate"},
            ]
        )

    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        service = TargetPreparationService(database.connection)
        campaign = service.add_csv(csv_path)
        assert len(campaign.candidates) == 2
        selected = service.select(campaign.campaign_id, campaign.candidates[1].candidate_id)
        repeated = service.select(campaign.campaign_id, campaign.candidates[1].candidate_id)

    assert selected.group_id == "group-2"
    assert selected.source == "csv"
    assert repeated == selected


def test_discovery_persists_keyword_location_candidates_and_one_selection(tmp_path: Path) -> None:
    discovery_html = b"""
    <section data-pgscan-discovery="1" data-keyword="garden" data-location="Bristol">
      <article data-pgscan-candidate="1" data-group-id="garden-1"
        data-canonical-url="https://example.test/groups/garden-1" data-name="Garden One"
        data-keyword-score="1" data-location-score="0.5"></article>
      <article data-pgscan-candidate="1" data-group-id="garden-2"
        data-canonical-url="https://example.test/groups/garden-2" data-name="Garden Two"
        data-keyword-score="0.9" data-location-score="1"></article>
    </section>
    """
    with Database(tmp_path / "scanner.sqlite3") as database:
        database.migrate()
        service = TargetPreparationService(database.connection)
        campaign = service.add_discovery(discovery_html, keyword="garden", location="Bristol")
        selected = service.select(campaign.campaign_id, campaign.candidates[0].candidate_id)
        query = database.connection.execute(
            "SELECT keyword, location FROM discovery_queries WHERE campaign_id = ?",
            (campaign.campaign_id,),
        ).fetchone()

    assert [candidate.group_id for candidate in campaign.candidates] == ["garden-2", "garden-1"]
    assert selected.group_id == "garden-2"
    assert selected.source == "discovery"
    assert dict(query) == {"keyword": "garden", "location": "Bristol"}
