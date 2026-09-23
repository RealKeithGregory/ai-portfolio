"""Production hardening: response headers, environment-aware API docs, and
the guards on the two POST endpoints.

The CSP tests come in pairs. One asserts the policy itself, the other asserts
that the templates still obey it -- a policy that forbids inline script is
only worth having if nothing in the site relies on inline script.
"""

import importlib
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import security
import server

TEMPLATES = sorted((Path(__file__).resolve().parent.parent / "templates").glob("*.html"))

EXPECTED_HEADERS = (
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Permissions-Policy",
)


@contextmanager
def app_built_with(**env):
    """Build an independent copy of the app under the given environment.

    `config`, `security` and `server` are re-executed behind temporarily
    replaced sys.modules entries, so the session-wide app that every other
    test shares is left exactly as it was.
    """
    names = ("config", "security", "server")
    saved_modules = {name: sys.modules.get(name) for name in names}
    saved_env = {key: os.environ.get(key) for key in env}
    try:
        os.environ.update(env)
        for name in names:
            sys.modules.pop(name, None)
        yield importlib.import_module("server").app
    finally:
        for key, value in saved_env.items():
            os.environ.pop(key, None) if value is None else os.environ.__setitem__(key, value)
        for name, module in saved_modules.items():
            sys.modules.pop(name, None) if module is None else sys.modules.__setitem__(name, module)


# ─── SECURITY HEADERS ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", ["/", "/blog", "/static/css/styles.css", "/not-a-page"])
def test_every_response_carries_the_security_headers(client, path):
    """Pages, static assets and error pages alike."""
    headers = client.get(path).headers
    for name in EXPECTED_HEADERS:
        assert name.lower() in headers, f"{name} missing from {path}"


def test_api_responses_carry_the_security_headers(client):
    headers = client.post("/api/search", json={"query": "evaluation"}).headers
    for name in EXPECTED_HEADERS:
        assert name.lower() in headers


def test_header_values_are_the_restrictive_ones(client):
    headers = client.get("/").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_csp_allows_no_inline_or_evaluated_script(client):
    csp = client.get("/").headers["content-security-policy"]
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp
    assert "script-src 'self'" in csp


def test_csp_pins_the_origins_the_site_actually_uses(client):
    csp = client.get("/").headers["content-security-policy"]
    assert "default-src 'self'" in csp
    # Google Fonts: the stylesheet and the font files it references.
    assert "style-src 'self' https://fonts.googleapis.com" in csp
    assert "font-src https://fonts.gstatic.com" in csp
    # The favicon is an inline SVG data: URI.
    assert "img-src 'self' data:" in csp


def test_csp_forbids_framing_and_plugins(client):
    csp = client.get("/").headers["content-security-policy"]
    for directive in ("frame-ancestors 'none'", "object-src 'none'",
                      "base-uri 'self'", "form-action 'self'"):
        assert directive in csp


# ─── THE TEMPLATES MUST OBEY THE POLICY ───────────────────────────────────────
@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_templates_use_no_inline_script(template):
    """An inline <script> block or an on*= handler would need
    script-src 'unsafe-inline', which is the directive worth keeping."""
    html = template.read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\ssrc=)", html), "inline <script> block"
    handlers = re.findall(r"\son[a-z]+\s*=", html)
    assert not handlers, f"inline event handler(s): {handlers}"
    assert "javascript:" not in html


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_templates_use_no_inline_style(template):
    """Inline style attributes would need style-src 'unsafe-inline'. The
    stagger and spacing classes in styles.css replace them."""
    html = template.read_text(encoding="utf-8")
    assert not re.search(r"\sstyle\s*=", html), "inline style attribute"


def test_stagger_classes_the_templates_use_are_defined():
    """The delay classes replaced inline transition-delay attributes, so a
    missing rule would silently drop the animation instead of erroring."""
    css = (Path(__file__).resolve().parent.parent / "public/css/styles.css").read_text()
    for rule in (".delay-0", ".delay-1", ".delay-2", ".section-flush-top"):
        assert rule in css, f"{rule} is used by a template but not defined"


# ─── HSTS IS PRODUCTION-ONLY ──────────────────────────────────────────────────
def test_no_hsts_in_development(client):
    """A plain-HTTP dev server must never pin a browser to HTTPS."""
    assert "strict-transport-security" not in client.get("/").headers


def test_hsts_in_production():
    with app_built_with(APP_ENV="production") as production_app:
        headers = TestClient(production_app).get("/no-such-page").headers
        assert headers["strict-transport-security"] == security.HSTS
        assert "preload" not in headers["strict-transport-security"]


# ─── INTERACTIVE DOCS ARE DEVELOPMENT-ONLY ────────────────────────────────────
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_are_available_in_development(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_interactive_docs_are_not_served_in_production(path):
    with app_built_with(APP_ENV="production") as production_app:
        assert TestClient(production_app).get(path).status_code == 404


def test_production_is_never_the_default():
    """A missing or misspelled APP_ENV has to fail towards development."""
    for value in ("", "prod", "Production ", "development", "staging"):
        with app_built_with(APP_ENV=value) as built:
            expected = value.strip().lower() == "production"
            assert (built.docs_url is None) is expected, value


# ─── RATE LIMITING ────────────────────────────────────────────────────────────
def test_configured_limits_cover_both_post_endpoints():
    assert set(security.RATE_LIMITS) == {"/api/search", "/api/chat"}
    search_limit, search_window = security.RATE_LIMITS["/api/search"]
    chat_limit, _ = security.RATE_LIMITS["/api/chat"]
    # Search runs embedding inference, so it is the tighter of the two.
    assert search_limit < chat_limit
    assert search_window == 60


def test_search_returns_429_once_the_limit_is_reached(client, monkeypatch):
    monkeypatch.setitem(server.api_limiter.limits, "/api/search", (3, 60))
    server.api_limiter.reset()
    for _ in range(3):
        assert client.post("/api/search", json={"query": "evaluation"}).status_code == 200

    limited = client.post("/api/search", json={"query": "evaluation"})
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1
    assert "rate limited" in limited.json()["detail"]


def test_rate_limited_response_still_carries_security_headers(client, monkeypatch):
    """The guard answers before the route, so it must sit inside the headers."""
    monkeypatch.setitem(server.api_limiter.limits, "/api/search", (1, 60))
    server.api_limiter.reset()
    client.post("/api/search", json={"query": "evaluation"})
    limited = client.post("/api/search", json={"query": "evaluation"})
    assert limited.status_code == 429
    for name in EXPECTED_HEADERS:
        assert name.lower() in limited.headers


def test_each_endpoint_has_its_own_allowance(client, monkeypatch):
    """Exhausting search must not lock a visitor out of the guide."""
    monkeypatch.setitem(server.api_limiter.limits, "/api/search", (1, 60))
    server.api_limiter.reset()
    client.post("/api/search", json={"query": "evaluation"})
    assert client.post("/api/search", json={"query": "evaluation"}).status_code == 429
    assert client.post("/api/chat", json={"message": "projects"}).status_code == 200


def test_pages_are_never_rate_limited(client, monkeypatch):
    """Reading the site is not an expensive operation and is not throttled."""
    monkeypatch.setitem(server.api_limiter.limits, "/api/search", (1, 60))
    server.api_limiter.reset()
    for _ in range(30):
        assert client.get("/").status_code == 200


def test_limiter_window_slides():
    """An allowance comes back once its window has passed."""
    limiter = security.RateLimiter({"/api/search": (2, 60)})
    assert limiter.retry_after("/api/search", "1.2.3.4", now=1000) is None
    assert limiter.retry_after("/api/search", "1.2.3.4", now=1001) is None
    assert limiter.retry_after("/api/search", "1.2.3.4", now=1002) is not None
    # Still blocked just before the first request ages out, free just after.
    assert limiter.retry_after("/api/search", "1.2.3.4", now=1059) is not None
    assert limiter.retry_after("/api/search", "1.2.3.4", now=1061) is None


def test_limiter_counts_each_client_separately():
    limiter = security.RateLimiter({"/api/search": (1, 60)})
    assert limiter.retry_after("/api/search", "1.2.3.4", now=1000) is None
    assert limiter.retry_after("/api/search", "1.2.3.4", now=1000) is not None
    assert limiter.retry_after("/api/search", "5.6.7.8", now=1000) is None


def test_limiter_ignores_unlisted_paths():
    limiter = security.RateLimiter({"/api/search": (1, 60)})
    for _ in range(100):
        assert limiter.retry_after("/", "1.2.3.4", now=1000) is None


def test_limiter_does_not_grow_without_bound():
    """Counters for clients that have gone away must be reclaimed."""
    limiter = security.RateLimiter({"/api/search": (5, 60)})
    for i in range(security.MAX_TRACKED_CLIENTS + 500):
        limiter.retry_after("/api/search", f"10.0.{i // 256}.{i % 256}", now=1000 + i)
    assert len(limiter._hits) <= security.MAX_TRACKED_CLIENTS


# ─── REQUEST BODY SIZE ────────────────────────────────────────────────────────
@pytest.mark.parametrize("path, field", [("/api/search", "query"), ("/api/chat", "message")])
def test_oversized_body_is_refused_before_it_is_read(client, path, field):
    oversized = {field: "x" * (security.MAX_BODY_BYTES + 1024)}
    response = client.post(path, json=oversized)
    assert response.status_code == 413
    assert "under" in response.json()["detail"]


@pytest.mark.parametrize("path, field", [("/api/search", "query"), ("/api/chat", "message")])
def test_bodies_within_the_limit_are_still_validated_normally(client, path, field):
    """Between the 500-character field limit and the body limit, the field
    validator is what rejects the request -- with a 422, not a 413."""
    assert client.post(path, json={field: "x" * 501}).status_code == 422
