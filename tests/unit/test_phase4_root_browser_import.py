"""Browser-profile import validation and source-preservation tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import app.session.browser as browser_module
from app.session.browser import _browser_copy_ignore, collect_imported_browser_profile_state
from app.session.profiles import SessionEnvelopeError


@pytest.mark.parametrize("profile_name", ["", ".", "..", "../Default", "Profile/2"])
def test_browser_import_rejects_invalid_profile_names(
    tmp_path: Path,
    profile_name: str,
) -> None:
    with pytest.raises(ValueError, match="profile name"):
        collect_imported_browser_profile_state(
            tmp_path,
            profile_name=profile_name,
        )


def test_browser_import_requires_user_data_root_contract(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="selected profile or Local State"):
        collect_imported_browser_profile_state(tmp_path)

    (tmp_path / "Default").mkdir()
    with pytest.raises(ValueError, match="selected profile or Local State"):
        collect_imported_browser_profile_state(tmp_path)


def test_browser_copy_omits_non_session_runtime_content() -> None:
    names = [
        "Cache",
        "Code Cache",
        "Cookies",
        "Extensions",
        "Local Storage",
        "Preferences",
        "Sessions",
    ]

    ignored = _browser_copy_ignore("C:/SOURCE/Default", names)

    assert ignored == {"Cache", "Code Cache", "Extensions", "Sessions"}
    assert {"Cookies", "Preferences", "Local Storage"}.isdisjoint(ignored)


def test_browser_import_reports_application_bound_profile_incompatibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "Default").mkdir()
    (tmp_path / "Local State").write_text(
        json.dumps({"os_crypt": {"app_bound_encrypted_key": "REDACTED"}}),
        encoding="utf-8",
    )

    class FakeContext:
        def storage_state(self) -> dict[str, object]:
            return {"cookies": [], "origins": []}

        def close(self) -> None:
            pass

    class FakeChromium:
        def launch_persistent_context(self, _: str, **__: Any) -> FakeContext:
            return FakeContext()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeManager:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(browser_module, "sync_playwright", FakeManager)

    with pytest.raises(SessionEnvelopeError, match="application-bound encryption"):
        collect_imported_browser_profile_state(tmp_path, channel="chrome")
