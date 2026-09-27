"""Production hardening: response headers and environment-aware API docs.

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
    # The script makes no requests of its own.
    assert "connect-src 'none'" in csp


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
    """The delay and spacing classes replaced inline style attributes, so a
    missing rule would silently drop the effect instead of erroring."""
    css = (Path(__file__).resolve().parent.parent / "assets/css/styles.css").read_text()
    used = set()
    for template in TEMPLATES:
        used |= set(re.findall(r"\b(delay-\d+|section-flush-top)\b", template.read_text(encoding="utf-8")))
    assert used, "expected at least one stagger or spacing class in the templates"
    for name in sorted(used):
        assert f".{name} " in css or f".{name}{{" in css, f".{name} is used by a template but not defined"


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
