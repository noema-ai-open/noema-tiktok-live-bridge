from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_AUTH_COOKIE_NAMES = {
    "sessionid",
    "sessionid_ss",
    "sid_tt",
    "sid_guard",
    "uid_tt",
    "uid_tt_ss",
}


def _profile_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "NOEMA" / "TikTokBridge" / "browser-profile"
    return Path.home() / ".noema" / "tiktok-browser-profile"


def _metadata_path() -> Path:
    return _profile_root().parent / "browser-session.json"


def _cookie_map(cookies: list[dict[str, Any]], *, include_auth: bool) -> dict[str, str]:
    result: dict[str, str] = {}
    for cookie in cookies:
        domain = str(cookie.get("domain") or "")
        if "tiktok.com" not in domain:
            continue
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        if not name or not value:
            continue
        if not include_auth and name in _AUTH_COOKIE_NAMES:
            continue
        result[name] = value
    return result


def _has_login(cookies: list[dict[str, Any]]) -> bool:
    names = {str(cookie.get("name") or "") for cookie in cookies}
    return bool({"sessionid", "sessionid_ss", "sid_tt"} & names)


class TikTokBrowserSession:
    """Local Edge/Chrome session for TikTok.

    NOEMA never receives a TikTok password. Sign-in happens inside an ordinary
    browser window backed by a dedicated local profile. Account-authentication
    cookies remain in that profile and are not forwarded to third-party signing
    services. Non-account browser cookies such as ttwid can be reused by the
    direct TikTokLive connector to better match a real browser session.
    """

    def __init__(self) -> None:
        self.profile_dir = _profile_root()
        self.metadata_file = _metadata_path()
        self._login_task: asyncio.Task[None] | None = None
        self._state = "idle"
        self._last_error: str | None = None
        self._logged_in = False
        self._browser = "Microsoft Edge"
        self._last_checked: str | None = None
        self._load_metadata()

    def _load_metadata(self) -> None:
        try:
            data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        self._logged_in = bool(data.get("logged_in"))
        self._browser = str(data.get("browser") or self._browser)
        self._last_checked = data.get("last_checked")

    def _save_metadata(self) -> None:
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "logged_in": self._logged_in,
            "browser": self._browser,
            "last_checked": self._last_checked,
        }
        self.metadata_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def payload(self) -> dict[str, object]:
        return {
            "state": self._state,
            "logged_in": self._logged_in,
            "browser": self._browser,
            "profile_exists": self.profile_dir.exists(),
            "last_checked": self._last_checked,
            "error": self._last_error,
        }

    async def _launch(self, *, headless: bool):
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Browser-Login-Komponente fehlt (playwright nicht installiert)") from exc

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        playwright = await async_playwright().start()
        last_error: Exception | None = None
        for channel, label in (("msedge", "Microsoft Edge"), ("chrome", "Google Chrome")):
            try:
                context = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    channel=channel,
                    headless=headless,
                    viewport=None if not headless else {"width": 1280, "height": 900},
                    args=["--disable-background-timer-throttling"],
                )
                self._browser = label
                return playwright, context
            except Exception as exc:
                last_error = exc
        await playwright.stop()
        raise RuntimeError(
            "Microsoft Edge oder Google Chrome konnte nicht für den TikTok-Login gestartet werden"
        ) from last_error

    async def start_login(self) -> dict[str, object]:
        if self._login_task is not None and not self._login_task.done():
            return self.payload()
        self._state = "opening"
        self._last_error = None
        self._login_task = asyncio.create_task(self._login_worker(), name="tiktok-browser-login")
        return self.payload()

    async def _login_worker(self) -> None:
        playwright = None
        context = None
        try:
            playwright, context = await self._launch(headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=60_000)
            self._state = "waiting_for_login"
            for _ in range(450):
                if page.is_closed():
                    raise RuntimeError("TikTok-Loginfenster wurde geschlossen")
                cookies = await context.cookies("https://www.tiktok.com")
                if _has_login(cookies):
                    self._logged_in = True
                    self._state = "logged_in"
                    self._last_checked = datetime.now(timezone.utc).isoformat()
                    self._save_metadata()
                    return
                await asyncio.sleep(2)
            raise RuntimeError("TikTok-Login hat innerhalb von 15 Minuten nicht abgeschlossen")
        except asyncio.CancelledError:
            self._state = "idle"
            raise
        except Exception as exc:
            self._state = "error"
            self._last_error = " ".join(str(exc).split())[:300]
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception:
                    pass

    async def refresh(self) -> dict[str, object]:
        if self._login_task is not None and not self._login_task.done():
            return self.payload()
        self._state = "checking"
        self._last_error = None
        playwright = None
        context = None
        try:
            playwright, context = await self._launch(headless=True)
            cookies = await context.cookies("https://www.tiktok.com")
            self._logged_in = _has_login(cookies)
            self._last_checked = datetime.now(timezone.utc).isoformat()
            self._state = "logged_in" if self._logged_in else "not_logged_in"
            self._save_metadata()
        except Exception as exc:
            self._state = "error"
            self._last_error = " ".join(str(exc).split())[:300]
        finally:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception:
                    pass
        return self.payload()

    async def apply_to_tiktoklive_defaults(self) -> dict[str, object]:
        if self._login_task is not None and not self._login_task.done():
            return {"applied": False, "reason": "login_in_progress"}
        playwright = None
        context = None
        try:
            playwright, context = await self._launch(headless=True)
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=60_000)
            cookies = await context.cookies()
            user_agent = await page.evaluate("navigator.userAgent")
            safe_cookies = _cookie_map(cookies, include_auth=False)
            from TikTokLive.client.web.web_settings import WebDefaults

            WebDefaults.web_client_cookies = {
                **WebDefaults.web_client_cookies,
                **safe_cookies,
            }
            WebDefaults.web_client_headers = {
                **WebDefaults.web_client_headers,
                "User-Agent": str(user_agent),
                "Referer": "https://www.tiktok.com/",
                "Origin": "https://www.tiktok.com",
            }
            self._logged_in = _has_login(cookies)
            self._last_checked = datetime.now(timezone.utc).isoformat()
            self._state = "logged_in" if self._logged_in else "browser_ready"
            self._save_metadata()
            return {
                "applied": True,
                "logged_in": self._logged_in,
                "cookie_count": len(safe_cookies),
                "has_ttwid": "ttwid" in safe_cookies,
            }
        finally:
            if context is not None:
                await context.close()
            if playwright is not None:
                await playwright.stop()

    async def check_room(self, username: str) -> dict[str, object]:
        username = username.strip().lstrip("@")
        if not username:
            raise ValueError("TikTok-Benutzername fehlt")
        playwright = None
        context = None
        try:
            playwright, context = await self._launch(headless=True)
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=60_000)
            result = await page.evaluate(
                """async (username) => {
                    const url = `/api-live/user/room/?aid=1988&sourceType=54&uniqueId=${encodeURIComponent(username)}`;
                    const response = await fetch(url, { credentials: 'include' });
                    let data = null;
                    try { data = await response.json(); } catch (_) {}
                    return { ok: response.ok, status: response.status, data };
                }""",
                username,
            )
            data = result.get("data") if isinstance(result, dict) else None
            user = (((data or {}).get("data") or {}).get("user") or {}) if isinstance(data, dict) else {}
            room_id = user.get("roomId") or user.get("room_id")
            live_status = user.get("status")
            return {
                "ok": bool(result.get("ok")) if isinstance(result, dict) else False,
                "http_status": result.get("status") if isinstance(result, dict) else None,
                "username": username,
                "room_id": room_id,
                "live_status": live_status,
                "is_live": live_status in (2, 3, "2", "3"),
            }
        finally:
            if context is not None:
                await context.close()
            if playwright is not None:
                await playwright.stop()

    async def reset(self) -> dict[str, object]:
        task = self._login_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._login_task = None
        shutil.rmtree(self.profile_dir, ignore_errors=True)
        try:
            self.metadata_file.unlink()
        except FileNotFoundError:
            pass
        self._logged_in = False
        self._state = "idle"
        self._last_error = None
        self._last_checked = None
        return self.payload()


_session = TikTokBrowserSession()


def get_browser_session() -> TikTokBrowserSession:
    return _session
