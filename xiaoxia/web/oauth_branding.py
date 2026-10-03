# -*- coding: utf-8 -*-
"""Public OAuth branding pages for Xiaoxia Calendar.

Keeps the existing private Xiaoxia vault available at /vault while exposing
Google-readable public pages at /, /privacy and /terms.
"""
from __future__ import annotations

from fastapi.responses import HTMLResponse

APP_NAME = "Xiaoxia Calendar"
CONTACT_EMAIL = "xiaoxia.lobster@gmail.com"
GOOGLE_SITE_VERIFICATION = "PcL1nNtPXB0_f44VAjepdQ7imkAo1ZKiHc0kUbOJJwc"

_STYLE = """
<style>
body{font-family:Arial,'Noto Sans TC',sans-serif;max-width:820px;margin:48px auto;padding:0 22px;line-height:1.7;color:#222}
h1{font-size:32px;margin-bottom:8px} h2{margin-top:28px} .muted{color:#666}
a{color:#2563eb} nav{margin:24px 0;padding:14px 0;border-top:1px solid #ddd;border-bottom:1px solid #ddd}
code{background:#f4f4f4;padding:2px 5px;border-radius:4px}
</style>
"""


def _page(title: str, body: str) -> str:
    verification_meta = (
        f"<meta name='google-site-verification' content='{GOOGLE_SITE_VERIFICATION}'>"
        if GOOGLE_SITE_VERIFICATION
        else ""
    )
    return (
        "<!doctype html><html lang='en'><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title>"
        f"{verification_meta}"
        f"{_STYLE}"
        f"</head><body>{body}</body></html>"
    )


HOME_HTML = _page(
    APP_NAME,
    f"""
<h1>{APP_NAME}</h1>
<p class='muted'>Private Google Calendar assistant for the Xiaoxia Discord bot.</p>
<p>{APP_NAME} helps its authorized user view, create, update, and delete events in the user's own Google Calendar through natural-language commands in a private Discord environment.</p>
<h2>Google Calendar access</h2>
<p>The application requests Google Calendar event access only to provide calendar features requested by the authorized user. It does not sell Google user data or use Calendar data for advertising.</p>
<nav><a href='/privacy'>Privacy Policy</a> &nbsp;·&nbsp; <a href='/terms'>Terms of Service</a> &nbsp;·&nbsp; <a href='/vault'>Private Xiaoxia Vault</a></nav>
<p>Contact: <a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a></p>
""",
)

PRIVACY_HTML = _page(
    f"{APP_NAME} Privacy Policy",
    f"""
<h1>{APP_NAME} Privacy Policy</h1>
<p class='muted'>Last updated: 2026-09-02</p>
<h2>What data we access</h2>
<p>{APP_NAME} may access Google Calendar event data for the Google account that explicitly authorizes the application. This can include event titles, descriptions, start/end times, attendees when present, and other event fields required to read or manage calendar events.</p>
<h2>How the data is used</h2>
<p>Google Calendar data is used only to provide user-requested calendar functions, including listing events, checking schedules, and creating, updating, or deleting events. The application does not use Google Calendar data for advertising, profiling, or sale.</p>
<h2>Data sharing</h2>
<p>Google user data is not sold. It is not shared with third parties except as technically necessary to operate the service or comply with applicable law. The service is intended for private use by the authorized user.</p>
<h2>Storage and retention</h2>
<p>The application may temporarily cache calendar information needed to execute scheduled tasks and avoid unnecessary repeated API calls. Data is retained only as needed for the service's operation and may be removed when no longer needed.</p>
<h2>Security</h2>
<p>OAuth credentials and tokens are kept in private server-side environment variables and are not intentionally exposed to public users.</p>
<h2>Your control and revocation</h2>
<p>You may revoke this application's Google access at any time from your Google Account security / third-party access settings. After access is revoked, the application can no longer access your Google Calendar through that authorization.</p>
<h2>Contact</h2>
<p>Questions about this policy may be sent to <a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a>.</p>
<nav><a href='/'>Home</a> &nbsp;·&nbsp; <a href='/terms'>Terms of Service</a></nav>
""",
)

TERMS_HTML = _page(
    f"{APP_NAME} Terms of Service",
    f"""
<h1>{APP_NAME} Terms of Service</h1>
<p class='muted'>Last updated: 2026-09-02</p>
<p>{APP_NAME} is a private calendar-assistant service provided for the authorized user's personal use.</p>
<h2>Use of the service</h2>
<p>The user is responsible for reviewing calendar actions and for maintaining control of the Google account and Discord environment connected to the service.</p>
<h2>Availability</h2>
<p>The service is provided on an as-is and as-available basis. Features may change, be interrupted, or be discontinued without guarantee of uninterrupted availability.</p>
<h2>Google authorization</h2>
<p>The service requires explicit Google OAuth authorization to access Calendar events. The user may revoke that authorization at any time.</p>
<h2>Acceptable use</h2>
<p>The service may not be used to access another person's Google account without that person's authorization or for unlawful activity.</p>
<h2>Contact</h2>
<p>Questions may be sent to <a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a>.</p>
<nav><a href='/'>Home</a> &nbsp;·&nbsp; <a href='/privacy'>Privacy Policy</a></nav>
""",
)


def install_oauth_branding_pages(app):
    api_app = getattr(app, "api_app", None)
    if api_app is None:
        raise RuntimeError("api_app not found")

    # Preserve the original private homepage at /vault.
    original_index = getattr(app, "read_index", None)

    # Remove only the existing GET / route so Google sees the public app page.
    removed = 0
    for route in list(api_app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in (getattr(route, "methods", set()) or set()):
            api_app.router.routes.remove(route)
            removed += 1

    @api_app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def oauth_brand_home():
        return HOME_HTML

    @api_app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
    async def oauth_privacy():
        return PRIVACY_HTML

    @api_app.get("/terms", response_class=HTMLResponse, include_in_schema=False)
    async def oauth_terms():
        return TERMS_HTML

    if original_index is not None and not any(getattr(r, "path", None) == "/vault" for r in api_app.router.routes):
        @api_app.get("/vault", response_class=HTMLResponse, include_in_schema=False)
        async def xiaoxia_private_vault():
            return await original_index()

    return {
        "module": "xiaoxia.web.oauth_branding",
        "public_routes": ["/", "/privacy", "/terms"],
        "vault_route": "/vault",
        "removed_legacy_root_routes": removed,
        "google_site_verification": bool(GOOGLE_SITE_VERIFICATION),
    }
