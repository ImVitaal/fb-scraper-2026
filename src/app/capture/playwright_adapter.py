"""Bounded, resumable Playwright capture for one rendered Group."""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, cast

from bs4 import BeautifulSoup
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import (
    Error as PlaywrightError,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from app.capture.rendered import RenderedPage, RenderedPageCapture

_POST_EXPANSION = re.compile(r"\b(see|show|read)\s+more\b", re.IGNORECASE)
_COMMENT_EXPANSION = re.compile(
    r"\b(view|show|load)\b.*\b(more|previous|all)?\s*comments?\b",
    re.IGNORECASE,
)
_REPLY = re.compile(r"\brepl(?:y|ies)\b", re.IGNORECASE)


@dataclass(frozen=True)
class BrowserCaptureLimits:
    """Hard limits for one browser capture lifecycle."""

    max_pages: int = 100
    max_interactions: int = 99
    max_retries: int = 2
    max_seconds: float = 300.0
    max_storage_bytes: int = 100 * 1024 * 1024
    navigation_timeout_ms: int = 30_000
    ready_timeout_ms: int = 3_000
    navigation_delay_seconds: float = 0.0
    scroll_delay_seconds: float = 0.0
    expansion_delay_seconds: float = 0.0
    retry_delays_seconds: tuple[float, ...] = ()
    max_recent_posts: int = 30

    def __post_init__(self) -> None:
        positive = {
            "max_pages": self.max_pages,
            "max_interactions": self.max_interactions,
            "max_seconds": self.max_seconds,
            "max_storage_bytes": self.max_storage_bytes,
            "navigation_timeout_ms": self.navigation_timeout_ms,
            "ready_timeout_ms": self.ready_timeout_ms,
            "max_recent_posts": self.max_recent_posts,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.max_retries < 0:
            raise ValueError("max_retries must be zero or greater")
        delays = {
            "navigation_delay_seconds": self.navigation_delay_seconds,
            "scroll_delay_seconds": self.scroll_delay_seconds,
            "expansion_delay_seconds": self.expansion_delay_seconds,
        }
        for name, value in delays.items():
            if value < 0:
                raise ValueError(f"{name} must be zero or greater")
        if any(value < 0 for value in self.retry_delays_seconds):
            raise ValueError("retry_delays_seconds values must be zero or greater")


class BrowserStateError(RuntimeError):
    """A rendered page reached an explicit non-success browser state."""

    def __init__(self, failure_class: str, message: str) -> None:
        self.failure_class = failure_class
        super().__init__(f"{failure_class}: {message}")


class CaptureBoundExceeded(BrowserStateError):
    """A configured browser capture bound stopped the run."""

    def __init__(self, bound: str, value: int | float) -> None:
        super().__init__(bound, f"capture exceeded {bound}={value}")


@dataclass(frozen=True)
class _Action:
    kind: str
    key: str
    selector: str | None = None
    text: str | None = None

    def payload(self) -> dict[str, str]:
        result = {"kind": self.kind, "key": self.key}
        if self.selector is not None:
            result["selector"] = self.selector
        if self.text is not None:
            result["text"] = self.text
        return result

    @classmethod
    def from_payload(cls, value: Mapping[str, object]) -> _Action:
        kind = value.get("kind")
        key = value.get("key")
        selector = value.get("selector")
        text = value.get("text")
        if not isinstance(kind, str) or not isinstance(key, str):
            raise BrowserStateError("checkpoint_invalid", "action fields are invalid")
        if selector is not None and not isinstance(selector, str):
            raise BrowserStateError("checkpoint_invalid", "selector is invalid")
        if text is not None and not isinstance(text, str):
            raise BrowserStateError("checkpoint_invalid", "text is invalid")
        return cls(kind, key, selector, text)


class _BrowserRenderedPageCapture:
    """Callable RenderedPageCapture backed by one persistent browser context."""

    def __init__(
        self,
        adapter: PlaywrightGroupCaptureAdapter,
        target_url: str,
        lower_bound: datetime | None,
    ) -> None:
        self._adapter = adapter
        self._target_url = target_url
        self._target_digest = sha256(target_url.encode()).hexdigest()
        self._lower_bound = lower_bound
        self._page: Page | None = None
        self._started_at = time.perf_counter()
        self._page_count = 0
        self._interaction_count = 0
        self._storage_bytes = 0
        self._completed: list[str] = []
        self._captured_post_ids: set[str] = set()
        self._pending: _Action | None = None
        self._stop_failure: BrowserStateError | None = None

    def __call__(self, checkpoint: str | None) -> RenderedPage:
        """Return rendered bytes and the opaque checkpoint for the next action."""
        self._ensure_time()
        if self._page_count >= self._adapter.limits.max_pages:
            raise CaptureBoundExceeded("page_limit", self._adapter.limits.max_pages)
        self._ensure_page(checkpoint)
        if checkpoint is not None:
            self._perform_checkpointed_action(checkpoint)
        assert self._page is not None
        self._wait_for_supported_state()
        raw_html = self._bounded_html(self._page.content())
        self._page_count += 1
        self._storage_bytes += len(raw_html)
        if self._storage_bytes > self._adapter.limits.max_storage_bytes:
            raise CaptureBoundExceeded(
                "storage_limit",
                self._adapter.limits.max_storage_bytes,
            )
        self._pending = self._derive_next_action()
        next_checkpoint = (
            self._encode_checkpoint(self._pending) if self._pending is not None else None
        )
        self._ensure_time()
        return RenderedPage(raw_html, next_checkpoint)

    def _ensure_page(self, checkpoint: str | None) -> None:
        if self._page is not None:
            return
        self._page = self._adapter._new_page()
        page = self._page
        page.on("response", self._on_response)
        self._retry(
            lambda: page.goto(
                self._target_url,
                wait_until="domcontentloaded",
                timeout=self._adapter.limits.navigation_timeout_ms,
            ),
            "navigation_failed",
        )
        self._wait_for_supported_state()
        self._wait_for_pacing(self._adapter.limits.navigation_delay_seconds)
        if checkpoint is None:
            return

        completed, pending = self._decode_checkpoint(checkpoint)
        for expected_key in completed:
            action = self._derive_next_action()
            if action is None or action.key != expected_key:
                raise BrowserStateError(
                    "checkpoint_invalid",
                    "rendered state does not match completed interaction history",
                )
            self._execute(action, replay=True)
            self._completed.append(action.key)
            self._wait_for_supported_state()
        derived = self._derive_next_action()
        if derived is None or derived.payload() != pending.payload():
            raise BrowserStateError(
                "checkpoint_invalid",
                "rendered state does not match the durable next action",
            )
        self._pending = derived

    def _perform_checkpointed_action(self, checkpoint: str) -> None:
        completed, pending = self._decode_checkpoint(checkpoint)
        if completed != self._completed:
            raise BrowserStateError(
                "checkpoint_invalid",
                "checkpoint interaction history does not match the open context",
            )
        if self._pending is None or pending.payload() != self._pending.payload():
            raise BrowserStateError(
                "checkpoint_invalid",
                "checkpoint does not match the expected next action",
            )
        self._execute(pending, replay=False)
        self._completed.append(pending.key)
        self._pending = None

    def _execute(self, action: _Action, *, replay: bool) -> None:
        self._ensure_time()
        self._raise_if_stop_requested()
        if self._interaction_count >= self._adapter.limits.max_interactions:
            raise CaptureBoundExceeded(
                "interaction_limit",
                self._adapter.limits.max_interactions,
            )
        assert self._page is not None
        page = self._page

        def operation() -> None:
            if action.kind == "scroll":
                page.evaluate("() => window.scrollBy(0, Math.max(window.innerHeight * 0.9, 600))")
                self._wait_for_pacing(self._adapter.limits.scroll_delay_seconds)
                return
            locator = (
                page.locator(action.selector)
                if action.selector is not None
                else page.get_by_role("button", name=action.text, exact=True).first
            )
            locator.click(timeout=self._adapter.limits.navigation_timeout_ms)
            self._wait_for_pacing(self._adapter.limits.expansion_delay_seconds)

        self._retry(operation, "interaction_failed")
        self._raise_if_stop_requested()
        self._interaction_count += 1
        self._ensure_time()
        if not replay:
            self._wait_for_supported_state()

    def _derive_next_action(self) -> _Action | None:
        assert self._page is not None
        permitted_post_ids = self._permitted_post_ids()
        for attribute, kind in (
            ("data-pgscan-expand-post", "expand_post"),
            ("data-pgscan-expand-comments", "expand_comments"),
        ):
            locator = self._page.locator(f"[{attribute}]")
            for index in range(locator.count()):
                candidate = locator.nth(index)
                if not candidate.is_visible():
                    continue
                value = candidate.get_attribute(attribute) or str(index)
                if value in self._adapter.known_post_ids:
                    self._adapter._record_known_post_skip(value)
                    continue
                if permitted_post_ids and value not in permitted_post_ids:
                    continue
                selector = f"[{attribute}={json.dumps(value)}]"
                return _Action(kind, f"{kind}:{value}", selector=selector)

        buttons = self._page.locator("button, [role='button']")
        for index in range(buttons.count()):
            candidate = buttons.nth(index)
            if not candidate.is_visible():
                continue
            label = " ".join(candidate.inner_text().split())
            if not label or _REPLY.search(label):
                continue
            post_id = self._post_id_for_button(candidate)
            if post_id is not None and post_id in self._adapter.known_post_ids:
                self._adapter._record_known_post_skip(post_id)
                continue
            if post_id is not None and permitted_post_ids and post_id not in permitted_post_ids:
                continue
            kind: str | None = None
            if _POST_EXPANSION.search(label):
                kind = "expand_post"
            elif _COMMENT_EXPANSION.search(label):
                kind = "expand_comments"
            if kind is not None:
                digest = sha256(label.encode()).hexdigest()[:16]
                return _Action(kind, f"{kind}:text:{digest}", text=label)

        if self._history_boundary_reached():
            return None
        scroll_number = sum(key.startswith("scroll:") for key in self._completed) + 1
        return _Action("scroll", f"scroll:{scroll_number}")

    def _permitted_post_ids(self) -> frozenset[str]:
        """Return the first bounded Post identifiers in current DOM order."""
        assert self._page is not None
        post_ids: list[str] = []
        anchors = self._page.locator("[data-pgscan-post-id], article a[href*='/posts/']")
        for index in range(anchors.count()):
            item = anchors.nth(index)
            explicit = item.get_attribute("data-pgscan-post-id")
            href = item.get_attribute("href") or ""
            match = re.search(r"/posts/([^/?#]+)", href)
            post_id = explicit or (match.group(1) if match else None)
            if post_id is not None and post_id not in post_ids:
                post_ids.append(post_id)
            if len(post_ids) >= self._adapter.limits.max_recent_posts:
                break
        return frozenset(post_ids)

    def _bounded_html(self, raw_html: str) -> bytes:
        """Exclude known and over-limit Posts from the normalized snapshot."""
        soup = BeautifulSoup(raw_html, "lxml")
        posts = list(soup.select("article"))
        posts.extend(
            post
            for post in soup.select("[data-pgscan-post-id]")
            if post.name != "article" and post.find_parent("article") is None
        )
        for post in posts:
            post_id = post.get("data-pgscan-post-id")
            if not post_id:
                link = post.select_one("a[href*='/posts/']")
                href = str(link.get("href", "")) if link is not None else ""
                match = re.search(r"/posts/([^/?#]+)", href)
                post_id = match.group(1) if match else None
            if post_id is None:
                continue
            post_id = str(post_id)
            if post_id in self._adapter.known_post_ids:
                self._adapter._record_known_post_skip(post_id)
                post.decompose()
                continue
            if post_id in self._captured_post_ids:
                continue
            if len(self._captured_post_ids) >= self._adapter.limits.max_recent_posts:
                post.decompose()
                continue
            self._captured_post_ids.add(post_id)
        return str(soup).encode("utf-8")

    @staticmethod
    def _post_id_for_button(candidate: Any) -> str | None:
        value = candidate.evaluate(
            """element => {
                const article = element.closest("article");
                if (!article) return null;
                const explicit = article.getAttribute("data-pgscan-post-id");
                if (explicit) return explicit;
                const link = article.querySelector("a[href*='/posts/']");
                if (!link) return null;
                const match = link.getAttribute("href").match(/\\/posts\\/([^/?#]+)/);
                return match ? match[1] : null;
            }"""
        )
        return value if isinstance(value, str) and value else None

    def _history_boundary_reached(self) -> bool:
        assert self._page is not None
        if len(self._captured_post_ids) >= self._adapter.limits.max_recent_posts:
            return True
        post_ids: set[str] = set()
        anchors = self._page.locator("[data-pgscan-post-id], article a[href*='/posts/']")
        for index in range(anchors.count()):
            item = anchors.nth(index)
            explicit = item.get_attribute("data-pgscan-post-id")
            if explicit:
                post_ids.add(explicit)
                continue
            href = item.get_attribute("href") or ""
            match = re.search(r"/posts/([^/?#]+)", href)
            if match:
                post_ids.add(match.group(1))
        if len(post_ids) >= self._adapter.limits.max_recent_posts:
            return True
        if self._page.locator(
            "[data-pgscan-history-boundary='reached'], [data-pgscan-content-end='true']"
        ).count():
            return True
        if self._lower_bound is None:
            return False
        values = self._page.locator("article time[datetime], [data-pgscan-post-id] time[datetime]")
        for index in range(values.count()):
            raw_value = values.nth(index).get_attribute("datetime")
            if raw_value is None:
                continue
            try:
                observed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            except ValueError:
                continue
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            if observed <= self._lower_bound:
                return True
        return False

    def _wait_for_supported_state(self) -> None:
        assert self._page is not None
        deadline = time.perf_counter() + self._adapter.limits.ready_timeout_ms / 1000
        while True:
            self._raise_if_stop_requested()
            failure = self._classify_failure()
            if failure is not None:
                raise failure
            if self._content_ready():
                return
            if time.perf_counter() >= deadline:
                raise BrowserStateError(
                    "layout_drift",
                    "explicit content-ready condition was not reached",
                )
            self._ensure_time()
            self._page.wait_for_timeout(50)

    def _classify_failure(self) -> BrowserStateError | None:
        assert self._page is not None
        url = self._page.url.lower()
        body = self._page.locator("body").inner_text(timeout=1_000).lower()
        conditions = (
            (
                "login_required",
                "[data-pgscan-login-required], form input[type='password']",
                ("/login",),
                ("log in", "login"),
            ),
            (
                "challenge",
                "[data-pgscan-challenge]",
                ("/challenge", "/checkpoint", "/captcha"),
                ("security check", "confirm your identity", "captcha", "checkpoint"),
            ),
            (
                "restricted",
                "[data-pgscan-restricted]",
                ("/restricted", "/locked"),
                (
                    "account temporarily restricted",
                    "account restricted",
                    "account locked",
                    "temporarily blocked",
                ),
            ),
            (
                "group_unavailable",
                "[data-pgscan-group-unavailable]",
                ("/unavailable",),
                ("this content is not available", "group is unavailable"),
            ),
        )
        for failure_class, selector, url_parts, text_parts in conditions:
            if (
                self._page.locator(selector).count()
                or any(part in url for part in url_parts)
                or any(part in body for part in text_parts)
            ):
                return BrowserStateError(failure_class, "browser reported a non-success state")
        return None

    def _content_ready(self) -> bool:
        assert self._page is not None
        return bool(
            self._page.locator(
                "[data-pgscan-content-ready='true'], [role='feed'], main article, div[role='main']"
            ).count()
        )

    def _retry(self, operation: Any, failure_class: str) -> Any:
        errors: list[PlaywrightError] = []
        for attempt in range(self._adapter.limits.max_retries + 1):
            self._ensure_time()
            self._raise_if_stop_requested()
            try:
                result = operation()
                self._raise_if_stop_requested()
                return result
            except (PlaywrightTimeoutError, PlaywrightError) as error:
                errors.append(error)
                self._raise_if_stop_requested()
                if attempt >= self._adapter.limits.max_retries:
                    break
                delay = self._retry_delay(attempt)
                self._wait_for_pacing(delay)
                self._adapter._record_retry(delay)
        raise BrowserStateError(
            failure_class,
            f"Playwright operation failed after {len(errors)} attempt(s)",
        ) from errors[-1]

    def _retry_delay(self, attempt: int) -> float:
        delays = self._adapter.limits.retry_delays_seconds
        if not delays:
            return 0.0
        return delays[min(attempt, len(delays) - 1)]

    def _wait_for_pacing(self, seconds: float) -> None:
        self._ensure_time()
        self._raise_if_stop_requested()
        if seconds <= 0:
            return
        assert self._page is not None
        remaining = self._adapter.limits.max_seconds - (time.perf_counter() - self._started_at)
        if remaining <= 0:
            raise CaptureBoundExceeded("time_limit", self._adapter.limits.max_seconds)
        if remaining < seconds:
            raise CaptureBoundExceeded("time_limit", self._adapter.limits.max_seconds)
        self._page.wait_for_timeout(seconds * 1000)
        self._ensure_time()
        self._raise_if_stop_requested()

    def _on_response(self, response: Any) -> None:
        status = getattr(response, "status", None)
        if status in {401, 403, 429} and self._stop_failure is None:
            self._stop_failure = BrowserStateError(
                f"http_{status}",
                f"browser response returned HTTP {status}",
            )
            self._adapter._record_stop(f"http_{status}")

    def _raise_if_stop_requested(self) -> None:
        if self._stop_failure is not None:
            raise self._stop_failure
        failure = self._classify_failure() if self._page is not None else None
        if failure is not None:
            self._adapter._record_stop(failure.failure_class)
            raise failure

    def _ensure_time(self) -> None:
        if time.perf_counter() - self._started_at > self._adapter.limits.max_seconds:
            raise CaptureBoundExceeded("time_limit", self._adapter.limits.max_seconds)

    def _encode_checkpoint(self, pending: _Action) -> str:
        payload = {
            "version": 1,
            "target": self._target_digest,
            "completed": self._completed,
            "pending": pending.payload(),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        digest = sha256(raw).hexdigest()[:24]
        return f"pgscan-v1.{encoded}.{digest}"

    def _decode_checkpoint(self, checkpoint: str) -> tuple[list[str], _Action]:
        try:
            prefix, encoded, expected_digest = checkpoint.split(".", 2)
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            payload = json.loads(raw)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            raise BrowserStateError("checkpoint_invalid", "checkpoint is malformed") from error
        if prefix != "pgscan-v1" or sha256(raw).hexdigest()[:24] != expected_digest:
            raise BrowserStateError("checkpoint_invalid", "checkpoint integrity check failed")
        if (
            not isinstance(payload, dict)
            or payload.get("version") != 1
            or payload.get("target") != self._target_digest
        ):
            raise BrowserStateError("checkpoint_invalid", "checkpoint target or version differs")
        completed = payload.get("completed")
        pending = payload.get("pending")
        if (
            not isinstance(completed, list)
            or not all(isinstance(value, str) for value in completed)
            or not isinstance(pending, dict)
        ):
            raise BrowserStateError("checkpoint_invalid", "checkpoint fields are invalid")
        return completed, _Action.from_payload(pending)


class PlaywrightGroupCaptureAdapter:
    """Own one Playwright context for a complete ``capture_pages`` call."""

    def __init__(
        self,
        storage_state: Mapping[str, object],
        *,
        limits: BrowserCaptureLimits | None = None,
        headless: bool = True,
        known_post_ids: set[str] | None = None,
    ) -> None:
        self.storage_state = dict(storage_state)
        self.limits = limits or BrowserCaptureLimits()
        self.headless = headless
        self.known_post_ids = frozenset(known_post_ids or ())
        self.closed = True
        self._retry_count = 0
        self._retry_waits: list[float] = []
        self._stop_reason: str | None = None
        self._known_post_skips: set[str] = set()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @contextmanager
    def capture_pages(
        self,
        target_url: str,
        *,
        lower_bound: datetime | None = None,
    ) -> Iterator[RenderedPageCapture]:
        """Yield a callback suitable for ``LiveCaptureWorkflow.capture_pages``.

        The browser and context remain open until the caller exits this manager.
        Exiting after success, failure, or interruption closes every resource.
        """
        if not target_url:
            raise ValueError("target_url must be non-empty")
        if not self.closed:
            raise RuntimeError("browser capture lifecycle is already open")
        self.closed = False
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context(storage_state=cast(Any, self.storage_state))
            yield _BrowserRenderedPageCapture(self, target_url, lower_bound)
        finally:
            self._close()

    def capture_group(self, target_url: str) -> bytes:
        """Capture the initial rendered page through a bounded browser lifecycle."""
        with self.capture_pages(target_url) as capture:
            return capture(None).raw_html

    def _new_page(self) -> Page:
        if self._context is None:
            raise RuntimeError("browser capture lifecycle is not open")
        return self._context.new_page()

    @property
    def protection_telemetry(self) -> dict[str, object]:
        """Return stable non-private pacing, retry, stop, and skip evidence."""
        return {
            "delays_seconds": {
                "expansion": self.limits.expansion_delay_seconds,
                "navigation": self.limits.navigation_delay_seconds,
                "scroll": self.limits.scroll_delay_seconds,
            },
            "known_posts_skipped": len(self._known_post_skips),
            "retry_count": self._retry_count,
            "retry_waits_seconds": list(self._retry_waits),
            "stop_reason": self._stop_reason,
        }

    def _record_retry(self, delay: float) -> None:
        self._retry_count += 1
        self._retry_waits.append(delay)

    def _record_stop(self, reason: str) -> None:
        if self._stop_reason is None:
            self._stop_reason = reason

    def _record_known_post_skip(self, post_id: str) -> None:
        self._known_post_skips.add(post_id)

    def _close(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
        finally:
            self._context = None
            try:
                if self._browser is not None:
                    self._browser.close()
            finally:
                self._browser = None
                if self._playwright is not None:
                    self._playwright.stop()
                self._playwright = None
                self.closed = True


__all__ = [
    "BrowserCaptureLimits",
    "BrowserStateError",
    "CaptureBoundExceeded",
    "PlaywrightGroupCaptureAdapter",
]
