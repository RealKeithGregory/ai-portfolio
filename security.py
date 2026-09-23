"""Response headers and API request guards.

Two pieces of plain Starlette middleware, no extra dependency:

1. `SecurityHeadersMiddleware` sets the same defensive headers on every
   response, including static files and API JSON.
2. `ApiGuardMiddleware` bounds the two POST endpoints -- a request body size
   limit and a per-IP rate limit -- so that embedding inference cannot be
   driven by an unbounded request rate from one client.

The rate limiter holds its counters in memory. That is correct for the way
this site is deployed (a single web process) and it is the reason the limits
stay modest; running more than one instance would need a shared store, and
each instance would otherwise enforce its own separate allowance.
"""

import ipaddress
import time
from collections import OrderedDict, deque

from starlette.responses import JSONResponse

# ─── CONTENT SECURITY POLICY ──────────────────────────────────────────────────
# Everything the site loads is either same-origin or Google Fonts:
#   - scripts:     /static/js/site.js only, with no inline script or handler
#   - styles:      /static/css/styles.css plus the Google Fonts stylesheet
#   - fonts:       fonts.gstatic.com, fetched by that stylesheet
#   - images:      the inline SVG favicon, which is a data: URI
#   - connections: fetch() to /api/search and /api/chat, same-origin
# so every directive below is the narrowest value the site actually works
# with. 'unsafe-inline' and 'unsafe-eval' appear nowhere.
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        # No plugins, no framing, and no way to retarget forms or relative URLs.
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)

# Browser features the site never uses. An empty allowlist denies them to the
# page and to anything it embeds.
PERMISSIONS_POLICY = ", ".join(
    f"{feature}=()"
    for feature in (
        "accelerometer", "autoplay", "camera", "display-capture", "geolocation",
        "gyroscope", "magnetometer", "microphone", "payment", "usb",
    )
)

# One year. `preload` is deliberately omitted: it is a slow commitment to
# undo and belongs to a domain owner's decision, not to an app default.
HSTS = "max-age=31536000; includeSubDomains"

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    # Stop browsers guessing a content type other than the one we send.
    "X-Content-Type-Options": "nosniff",
    # Belt and braces with CSP frame-ancestors, for older browsers.
    "X-Frame-Options": "DENY",
    # Send the full referrer within the site, only the origin off-site.
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": PERMISSIONS_POLICY,
}


class SecurityHeadersMiddleware:
    """Adds the headers above to every response.

    HSTS is applied only when the caller says the site is served over HTTPS,
    because sending it from a plain-HTTP development server would pin the
    browser to a scheme that server does not speak.
    """

    def __init__(self, app, hsts=False):
        self.app = app
        self.headers = dict(SECURITY_HEADERS)
        if hsts:
            self.headers["Strict-Transport-Security"] = HSTS

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                for name, value in self.headers.items():
                    headers.append((name.lower().encode(), value.encode()))
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ─── CLIENT IDENTITY ──────────────────────────────────────────────────────────
# Which address the rate limiter counts against.
#
# X-Forwarded-For is a list that every proxy appends to, so the entries a
# visitor can write sit on the LEFT and the entry the platform's front end
# added sits on the RIGHT. A request forged with "X-Forwarded-For: 9.9.9.9"
# reaches this app as "9.9.9.9, <the address the front end actually saw>".
# Counting from the right is therefore the only position a visitor cannot
# choose, and the only one a rate limit can be keyed on.
#
# This is also why uvicorn's --proxy-headers is not used. With
# --forwarded-allow-ips='*' it rewrites the client address from the
# left-most entry, which is exactly the spoofable one.
#
# TRUSTED_PROXY_HOPS is how many proxies in front of this app may be
# believed. On Cloud Run that is one: Google's front end. With no proxy at
# all (local development) there is no header and the socket peer is used.
TRUSTED_PROXY_HOPS = 1


def _forwarded_entries(scope):
    """Every X-Forwarded-For value, in the order the proxies appended them."""
    entries = []
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            entries += value.decode("latin1").split(",")
    return [entry.strip() for entry in entries if entry.strip()]


# An IPv6 visitor is normally handed a whole /64 and can move freely inside
# it: privacy extensions rotate the host bits on a schedule, without the
# visitor doing anything. Keying on the full address would hand one visitor
# effectively unlimited allowances, so IPv6 is counted per network prefix,
# which is the part that identifies the subscriber. IPv4 is used as-is.
IPV6_PREFIX_BITS = 64


def _as_key(value):
    """Normalise an address into a rate-limit key, or None if it is not one."""
    try:
        parsed = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return None
    if parsed.version == 6:
        network = ipaddress.ip_network(f"{parsed}/{IPV6_PREFIX_BITS}", strict=False)
        return f"{network.network_address}/{IPV6_PREFIX_BITS}"
    return str(parsed)


def client_identity(scope, trusted_hops=TRUSTED_PROXY_HOPS):
    """The rate-limit key, taken from the right of X-Forwarded-For.

    IPv6 addresses are reduced to their /64 network, so a visitor cannot
    multiply their allowance simply by rotating inside their own prefix.

    Falls back to the socket peer whenever the header is absent, shorter
    than the number of proxies we expect, or not an address -- all of which
    mean the request did not arrive the way production says it does.
    """
    raw_peer = scope["client"][0] if scope.get("client") else "unknown"
    peer = _as_key(raw_peer) or raw_peer
    if trusted_hops < 1:
        return peer
    entries = _forwarded_entries(scope)
    if len(entries) < trusted_hops:
        return peer
    return _as_key(entries[-trusted_hops]) or peer


# ─── API GUARDS ───────────────────────────────────────────────────────────────
# Requests per window (seconds), per client IP, per path. /api/search runs
# embedding inference and is the endpoint worth protecting; /api/chat only
# matches keywords, so it is cheaper and gets a looser allowance. Both are
# well above what a person clicking around the page can reach, and well
# below what a script could use to keep the CPU busy.
RATE_LIMITS = {
    "/api/search": (20, 60),
    "/api/chat": (40, 60),
}

# Both endpoints take one short string (max 500 characters). Anything near
# this size is already malformed, and rejecting on Content-Length means an
# oversized body is refused before it is read into memory.
MAX_BODY_BYTES = 16 * 1024

# Upper bound on the number of clients tracked at once, so the counters
# cannot grow without limit. Stale entries are dropped first; if every entry
# is live, the oldest is evicted.
MAX_TRACKED_CLIENTS = 4096


class RateLimiter:
    """Sliding window of request timestamps per (path, client)."""

    def __init__(self, limits=None):
        self.limits = dict(RATE_LIMITS if limits is None else limits)
        self._hits = OrderedDict()

    def retry_after(self, path, client, now=None):
        """Seconds the client must wait, or None when the request is allowed."""
        rule = self.limits.get(path)
        if rule is None:
            return None
        limit, window = rule
        now = time.monotonic() if now is None else now

        hits = self._hits.get((path, client))
        if hits is None:
            hits = self._hits[(path, client)] = deque()
        self._hits.move_to_end((path, client))

        cutoff = now - window
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= limit:
            # The window frees up when its oldest request falls out of it.
            return max(1, int(window - (now - hits[0])) + 1)

        hits.append(now)
        self._prune(now)
        return None

    def _prune(self, now):
        if len(self._hits) <= MAX_TRACKED_CLIENTS:
            return
        for key in list(self._hits):
            _, window = self.limits[key[0]]
            if not self._hits[key] or self._hits[key][-1] <= now - window:
                del self._hits[key]
        while len(self._hits) > MAX_TRACKED_CLIENTS:
            self._hits.popitem(last=False)

    def reset(self):
        """Drop all counters. Used by the tests to isolate cases."""
        self._hits.clear()


class ApiGuardMiddleware:
    """Body-size and rate limits for the rate-limited API paths.

    Page requests are untouched: a visitor reading the site is never
    throttled, only the two endpoints that do work on demand.
    """

    def __init__(self, app, limiter=None, max_body_bytes=MAX_BODY_BYTES):
        self.app = app
        self.limiter = limiter if limiter is not None else RateLimiter()
        self.max_body_bytes = max_body_bytes
        self.paths = frozenset(self.limiter.limits)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] not in self.paths:
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        try:
            declared = int(headers.get("content-length", 0))
        except ValueError:
            declared = 0
        if declared > self.max_body_bytes:
            await self._reject(
                scope, receive, send, 413,
                f"Request body must be under {self.max_body_bytes} bytes.",
            )
            return

        wait = self.limiter.retry_after(scope["path"], client_identity(scope))
        if wait is not None:
            await self._reject(
                scope, receive, send, 429,
                "Too many requests. This endpoint runs a model locally, so it is "
                f"rate limited. Try again in {wait} second(s).",
                headers={"Retry-After": str(wait)},
            )
            return

        await self.app(scope, receive, send)

    async def _reject(self, scope, receive, send, status, detail, headers=None):
        # Sending the response from here means the request body is never read.
        # The security headers middleware wraps this one, so it still sees the
        # response and adds its own headers to it.
        response = JSONResponse({"detail": detail}, status_code=status, headers=headers)
        await response(scope, receive, send)
