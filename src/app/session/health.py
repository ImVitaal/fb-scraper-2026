"""Authenticated route probing and explicit session-health classification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import StorageState as PlaywrightStorageState
from playwright.sync_api import sync_playwright


class SessionHealth(StrEnum):
    """Operator-visible authenticated-session states."""

    READY = "ready"
    EXPIRED = "expired"
    CHALLENGED = "challenged"
    RESTRICTED = "restricted"
    INVALID = "invalid"


@dataclass(frozen=True)
class ProbeObservation:
    """Minimal probe input. Text and routes never enter the result."""

    status_code: int | None
    route: str
    page_text: str
    navigation_error: bool = False


@dataclass(frozen=True)
class SessionHealthResult:
    """Non-secret health result."""

    health: SessionHealth
    evidence: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"health": self.health.value, "evidence": list(self.evidence)}


class SessionProbe(Protocol):
    """Common probe boundary used by imported and guided profiles."""

    def __call__(
        self,
        route: str,
        storage_state: Mapping[str, object],
    ) -> ProbeObservation: ...


def classify_observation(observation: ProbeObservation) -> SessionHealthResult:
    """Classify an observation without retaining response content or routes."""
    if observation.navigation_error or observation.status_code is None:
        return SessionHealthResult(SessionHealth.INVALID, ("navigation_failed",))

    route = observation.route.casefold()
    text = observation.page_text.casefold()
    if any(marker in route or marker in text for marker in ("checkpoint", "security check")):
        return SessionHealthResult(SessionHealth.CHALLENGED, ("challenge_detected",))
    if observation.status_code == 401 or any(
        marker in route or marker in text
        for marker in ("/login", "login required", "session expired", "sign in")
    ):
        return SessionHealthResult(SessionHealth.EXPIRED, ("authentication_required",))
    if observation.status_code == 403 or any(
        marker in text
        for marker in ("access restricted", "temporarily blocked", "permission denied")
    ):
        return SessionHealthResult(SessionHealth.RESTRICTED, ("access_restricted",))
    if 200 <= observation.status_code < 400:
        return SessionHealthResult(SessionHealth.READY, ("authenticated_route_reached",))
    return SessionHealthResult(SessionHealth.INVALID, ("unexpected_response",))


def probe_with_playwright(
    route: str,
    storage_state: Mapping[str, object],
    *,
    headless: bool = True,
) -> ProbeObservation:
    """Navigate one lightweight route using a supplied encrypted-profile state."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                context = browser.new_context(
                    storage_state=cast(PlaywrightStorageState, dict(storage_state))
                )
                try:
                    page = context.new_page()
                    response = page.goto(route, wait_until="domcontentloaded")
                    status = response.status if response is not None else None
                    return ProbeObservation(status, page.url, page.locator("body").inner_text())
                finally:
                    context.close()
            finally:
                browser.close()
    except PlaywrightError:
        return ProbeObservation(None, "", "", navigation_error=True)
