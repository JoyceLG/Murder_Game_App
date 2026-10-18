"""What the nginx front adds on top of the app: headers, caching, SPA routing, proxying."""

import re

import pytest

pytestmark = pytest.mark.nginx


def test_security_headers_on_the_app(api):
    response = api.get("/")
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_index_has_no_inline_script_the_csp_would_block(api):
    html = api.get("/").text
    assert "onload=" not in html
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html)


def test_index_and_translations_are_never_cached(api):
    for path in ("/", "/i18n/fr.json", "/i18n/en.json"):
        response = api.get(path)
        assert response.status_code == 200, path
        assert "no-cache" in response.headers["cache-control"], path


def test_hashed_bundles_are_cached_long(api):
    bundle = re.search(r'src="([^"]+\.js)"', api.get("/").text).group(1)
    response = api.get(f"/{bundle}")
    assert response.status_code == 200
    assert "max-age=31536000" in response.headers["cache-control"]


def test_deep_links_serve_the_app(api):
    response = api.get("/g/ABCD/play")
    assert response.status_code == 200
    assert "<app-root>" in response.text


def test_api_and_health_are_proxied(api):
    assert api.get("/health").json() == {"status": "ok"}
    assert api.get("/games/ZZZZ").status_code == 404
