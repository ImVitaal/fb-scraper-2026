"""Browser-profile import validation and source-preservation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.session.browser import _browser_copy_ignore, collect_imported_browser_profile_state


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


def test_browser_copy_omits_disposable_caches_only() -> None:
    names = ["Cache", "Code Cache", "Cookies", "Preferences", "Local Storage"]

    ignored = _browser_copy_ignore("C:/SOURCE/Default", names)

    assert ignored == {"Cache", "Code Cache"}
    assert {"Cookies", "Preferences", "Local Storage"}.isdisjoint(ignored)
