from app.tiktok.browser_session import _cookie_map, _has_login


def test_browser_cookie_map_keeps_tiktok_browser_state_but_not_account_auth() -> None:
    cookies = [
        {"domain": ".tiktok.com", "name": "ttwid", "value": "browser-id"},
        {"domain": ".tiktok.com", "name": "msToken", "value": "ms-token"},
        {"domain": ".tiktok.com", "name": "sessionid", "value": "secret-session"},
        {"domain": ".example.com", "name": "other", "value": "ignore-me"},
    ]

    safe = _cookie_map(cookies, include_auth=False)

    assert safe == {"ttwid": "browser-id", "msToken": "ms-token"}
    assert "sessionid" not in safe


def test_browser_login_detection_accepts_common_tiktok_session_cookie_names() -> None:
    assert _has_login([{"domain": ".tiktok.com", "name": "sessionid", "value": "x"}])
    assert _has_login([{"domain": ".tiktok.com", "name": "sid_tt", "value": "x"}])
    assert not _has_login([{"domain": ".tiktok.com", "name": "ttwid", "value": "x"}])
