import re
import time

import httpx
from fastapi import Request
from fastapi.responses import Response

from session import get_cookies, save_cookies

TARGET = "https://app.stealthwriter.ai"

_DROP_REQUEST_HEADERS = {
    "host", "content-length", "transfer-encoding", "connection",
    "keep-alive", "upgrade", "te", "trailers", "proxy-authorization",
    "accept-encoding",
}

_DROP_RESPONSE_HEADERS = {
    "content-encoding", "transfer-encoding", "content-length",
    "connection", "server", "x-frame-options", "content-security-policy",
}

_BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "DNT": "1",
    "sec-ch-ua": '"Google Chrome";v="147", "Chromium";v="147", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

_cache: dict[str, tuple] = {}
_STATIC_EXTS = {".js", ".css", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".svg", ".gif", ".ttf"}
_CACHE_TTL = 600


def _is_static(path: str) -> bool:
    return any(path.split("?")[0].endswith(ext) for ext in _STATIC_EXTS)


def _capture_auth_cookies(resp: httpx.Response):
    """If StealthWriter sets session cookies (e.g. after login), save them so
    subsequent requests are authenticated automatically."""
    new_cookies = {}
    for value in resp.headers.get_list("set-cookie"):
        parts = value.split(";")
        if not parts:
            continue
        name_value = parts[0].strip()
        if "=" not in name_value:
            continue
        name, val = name_value.split("=", 1)
        name = name.strip()
        val = val.strip()
        # Capture any auth/session cookies StealthWriter issues
        if any(kw in name.lower() for kw in ("session", "auth", "token")):
            new_cookies[name] = val

    if new_cookies:
        existing = get_cookies()
        existing.update(new_cookies)
        save_cookies(existing)


def _rewrite_html(html: str) -> str:
    # Route all absolute StealthWriter links through our proxy
    html = html.replace("https://app.stealthwriter.ai", "")
    html = html.replace("http://app.stealthwriter.ai", "")
    return html


async def proxy_request(path: str, request: Request) -> Response:
    cookies = get_cookies()

    url = f"{TARGET}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    # Cache for static assets
    if request.method == "GET" and _is_static(path):
        cached = _cache.get(url)
        if cached:
            content, status, headers, media_type, expires_at = cached
            if time.time() < expires_at:
                return Response(content=content, status_code=status, headers=headers, media_type=media_type)
            del _cache[url]

    # Build request headers
    fwd_headers = {**_BASE_HEADERS}
    for k, v in request.headers.items():
        if k.lower() not in _DROP_REQUEST_HEADERS:
            fwd_headers[k] = v
    fwd_headers["host"] = "app.stealthwriter.ai"
    fwd_headers["origin"] = TARGET
    fwd_headers["referer"] = f"{TARGET}/dashboard"

    # Force all cookies into a single Cookie header (bypasses httpx domain matching)
    if cookies:
        fwd_headers["cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

    body = await request.body()

    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers={}) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=fwd_headers,
                content=body,
            )
        except httpx.RequestError as exc:
            return Response(content=f"Proxy connection error: {exc}", status_code=502)

    # Auto-save any session cookies StealthWriter sets (e.g. after login)
    _capture_auth_cookies(resp)

    content = resp.content
    media_type = resp.headers.get("content-type", "application/octet-stream")

    if "text/html" in media_type:
        content = _rewrite_html(content.decode("utf-8", errors="replace")).encode("utf-8")

    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in _DROP_RESPONSE_HEADERS
    }
    if "location" in resp_headers:
        resp_headers["location"] = resp_headers["location"].replace(TARGET, "")

    if request.method == "GET" and _is_static(path) and resp.status_code == 200:
        _cache[url] = (content, resp.status_code, dict(resp_headers), media_type, time.time() + _CACHE_TTL)

    return Response(
        content=content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=media_type,
    )
