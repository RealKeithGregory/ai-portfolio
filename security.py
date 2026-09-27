"""Response headers.

`SecurityHeadersMiddleware` is plain Starlette middleware with no extra
dependency. It sets the same defensive headers on every response, including
static files and error pages.
"""

# ─── CONTENT SECURITY POLICY ──────────────────────────────────────────────────
# Everything the site loads is either same-origin or Google Fonts:
#   - scripts:     /static/js/site.js only, with no inline script or handler
#   - styles:      /static/css/styles.css plus the Google Fonts stylesheet
#   - fonts:       fonts.gstatic.com, fetched by that stylesheet
#   - images:      the inline SVG favicon, which is a data: URI
#   - connections: none; the script makes no requests of its own
# so every directive below is the narrowest value the site actually works
# with. 'unsafe-inline' and 'unsafe-eval' appear nowhere.
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data:",
        "connect-src 'none'",
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
