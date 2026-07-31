"""Encrypted browser-session support."""

from app.session.browser import (
    NormalChromeAttachmentFailure,
    NormalChromeAttachmentTimeout,
    collect_guided_storage_state,
    collect_imported_browser_profile_state,
    collect_normal_chrome_attachment_state,
    launch_normal_chrome_attachment,
)
from app.session.health import SessionHealth, SessionHealthResult, probe_with_playwright
from app.session.profiles import SessionMetadata, SessionProfileService

__all__ = [
    "NormalChromeAttachmentFailure",
    "NormalChromeAttachmentTimeout",
    "SessionHealth",
    "SessionHealthResult",
    "SessionMetadata",
    "SessionProfileService",
    "collect_guided_storage_state",
    "collect_imported_browser_profile_state",
    "collect_normal_chrome_attachment_state",
    "launch_normal_chrome_attachment",
    "probe_with_playwright",
]
