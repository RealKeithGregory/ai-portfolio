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


# ─── CLIENT IDENTITY BEHIND A PROXY ───────────────────────────────────────────
# The rate limiter is only as good as the address it counts against. These
# tests pin down which X-Forwarded-For position is trusted, because trusting
# the wrong one lets any visitor reset their own allowance at will.
def scope_with(forwarded=None, peer="10.0.0.1"):
    headers = []
    for value in [] if forwarded is None else forwarded:
        headers.append((b"x-forwarded-for", value.encode()))
    return {"type": "http", "headers": headers, "client": (peer, 1234)}


def test_client_identity_is_the_address_the_front_end_appended():
    """One proxy in front: the right-most entry is the real client."""
    assert security.client_identity(scope_with(["203.0.113.7"])) == "203.0.113.7"


def test_forged_forwarded_header_cannot_choose_the_identity():
    """A visitor sending their own X-Forwarded-For has it appended to, not
    replaced, so the forged values land on the left and are ignored."""
    forged = scope_with(["9.9.9.9, 203.0.113.7"])
    assert security.client_identity(forged) == "203.0.113.7"

    many = scope_with(["1.1.1.1, 2.2.2.2, 3.3.3.3, 203.0.113.7"])
    assert security.client_identity(many) == "203.0.113.7"


def test_forged_header_split_across_several_headers_is_still_ignored():
    """Proxies may merge repeated headers or leave them separate."""
    split = scope_with(["9.9.9.9", "8.8.8.8, 203.0.113.7"])
    assert security.client_identity(split) == "203.0.113.7"


def test_identity_falls_back_to_the_socket_peer():
    """No header (local development), an empty one, or one too short to
    contain the hop we expect: none of these is a client address."""
    assert security.client_identity(scope_with(None)) == "10.0.0.1"
    assert security.client_identity(scope_with([""])) == "10.0.0.1"
    assert security.client_identity(scope_with([" , "])) == "10.0.0.1"
    assert security.client_identity(scope_with(["1.1.1.1"]), trusted_hops=2) == "10.0.0.1"


def test_identity_rejects_a_value_that_is_not_an_address():
    """Otherwise the key space is whatever a visitor decides to type."""
    assert security.client_identity(scope_with(["not-an-ip"])) == "10.0.0.1"
    assert security.client_identity(scope_with(["9.9.9.9, evil"])) == "10.0.0.1"


def test_ipv6_is_counted_per_network_not_per_address():
    """A visitor's IPv6 host bits rotate on their own, so counting the full
    address would hand one subscriber an unlimited supply of allowances."""
    first = security.client_identity(scope_with(["2001:db8:abcd:1234::1"]))
    rotated = security.client_identity(scope_with(["2001:db8:abcd:1234:9999:8888:7777:6666"]))
    bracketed = security.client_identity(scope_with(["[2001:db8:abcd:1234::abc]"]))
    assert first == rotated == bracketed == "2001:db8:abcd:1234::/64"

    other_network = security.client_identity(scope_with(["2001:db8:abcd:9999::1"]))
    assert other_network != first


def test_ipv4_is_counted_per_address():
    assert security.client_identity(scope_with(["203.0.113.7"])) == "203.0.113.7"


def test_rotating_inside_an_ipv6_prefix_does_not_reset_the_limit(client, monkeypatch):
    monkeypatch.setitem(server.api_limiter.limits, "/api/search", (2, 60))
    server.api_limiter.reset()
    for host in ["2001:db8:1:2::1", "2001:db8:1:2::2"]:
        sent = client.post("/api/search", json={"query": "x"},
                           headers={"X-Forwarded-For": host})
        assert sent.status_code == 200
    blocked = client.post("/api/search", json={"query": "x"},
                          headers={"X-Forwarded-For": "2001:db8:1:2:aaaa:bbbb:cccc:dddd"})
    assert blocked.status_code == 429, "rotating within the /64 bought another request"
    elsewhere = client.post("/api/search", json={"query": "x"},
                            headers={"X-Forwarded-For": "2001:db8:1:3::1"})
    assert elsewhere.status_code == 200, "a different /64 must keep its own allowance"


def test_cloud_run_expects_exactly_one_trusted_hop():
    """Google's front end is the only proxy in front of this service."""
    assert security.TRUSTED_PROXY_HOPS == 1


# In production the front end appends the address it saw, so a visitor at
# 203.0.113.7 who sends nothing arrives as "203.0.113.7", and one who sends
# a forged header arrives as "<forged>, 203.0.113.7". These helpers build
# both shapes so the test exercises what Cloud Run actually delivers.
VISITOR = "203.0.113.7"


def as_cloud_run(forged=None):
    value = VISITOR if forged is None else f"{forged}, {VISITOR}"
    return {"X-Forwarded-For": value}


def test_spoofed_header_cannot_bypass_the_rate_limit(client, monkeypatch):
    """The whole point: rotating X-Forwarded-For must not buy more requests."""
    monkeypatch.setitem(server.api_limiter.limits, "/api/search", (2, 60))
    server.api_limiter.reset()
    for _ in range(2):
        sent = client.post("/api/search", json={"query": "x"}, headers=as_cloud_run())
        assert sent.status_code == 200

    for forged in ["9.9.9.9", "1.2.3.4", "203.0.113.99, 8.8.8.8", "not-an-ip"]:
        blocked = client.post(
            "/api/search", json={"query": "x"}, headers=as_cloud_run(forged)
        )
        assert blocked.status_code == 429, f"{forged!r} bought another request"


def test_a_different_visitor_still_gets_their_own_allowance(client, monkeypatch):
    """Keying on the appended entry must not collapse everyone into one
    bucket -- that would rate limit the whole internet together."""
    monkeypatch.setitem(server.api_limiter.limits, "/api/search", (1, 60))
    server.api_limiter.reset()
    first = client.post("/api/search", json={"query": "x"}, headers=as_cloud_run())
    assert first.status_code == 200
    assert client.post(
        "/api/search", json={"query": "x"}, headers=as_cloud_run()
    ).status_code == 429

    other = client.post(
        "/api/search", json={"query": "x"}, headers={"X-Forwarded-For": "198.51.100.4"}
    )
    assert other.status_code == 200


def test_the_trust_assumption_is_the_deployment_topology():
    """With one trusted hop, a lone entry IS believed. That is correct only
    because nothing can reach the container except through Google's front
    end, which always appends. Run this app with its port exposed directly
    and the header becomes forgeable again -- so this is pinned as a test,
    not left as a comment."""
    assert security.client_identity(scope_with(["9.9.9.9"])) == "9.9.9.9"
    assert security.client_identity(scope_with(["9.9.9.9"]), trusted_hops=0) == "10.0.0.1"
