import asyncio
import time
from urllib.parse import urljoin

import httpx
from fastapi import Request
from fastapi.responses import Response

from session import get_cookies

TARGET = "https://app.stealthwriter.ai"

# Headers to strip before forwarding to the target
_DROP_REQUEST_HEADERS = {
    "host", "content-length", "transfer-encoding", "connection",
    "keep-alive", "upgrade", "te", "trailers", "proxy-authorization",
    "accept-encoding",  # let httpx handle decompression transparently
}

# Headers to strip from the target's response before returning to the client
_DROP_RESPONSE_HEADERS = {
    "content-encoding", "transfer-encoding", "content-length",
    "connection", "server", "x-frame-options", "content-security-policy",
}

# Browser-like headers to attach to every forwarded request
_BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",  # force uncompressed so we can rewrite and forward cleanly
    "DNT": "1",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# Simple in-memory cache: url -> (content, status, headers, media_type, expires_at)
_cache: dict[str, tuple] = {}
_STATIC_EXTS = {".js", ".css", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".svg", ".gif", ".ttf"}
_CACHE_TTL = 600  # 10 minutes for static assets


def _is_static(path: str) -> bool:
    return any(path.split("?")[0].endswith(ext) for ext in _STATIC_EXTS)


def _rewrite_html(html: str, base_url: str) -> str:
    """Replace absolute stealthwriter URLs so they route through our proxy."""
    return (
        html
        .replace("https://app.stealthwriter.ai", "")
        .replace("http://app.stealthwriter.ai", "")
    )


async def proxy_request(path: str, request: Request) -> Response:
    cookies = get_cookies()

    url = f"{TARGET}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    # Serve from cache for static assets
    if request.method == "GET" and _is_static(path):
        cached = _cache.get(url)
        if cached:
            content, status, headers, media_type, expires_at = cached
            if time.time() < expires_at:
                return Response(content=content, status_code=status, headers=headers, media_type=media_type)
            del _cache[url]

    # Build forwarded headers
    fwd_headers = {**_BASE_HEADERS}
    for k, v in request.headers.items():
        if k.lower() not in _DROP_REQUEST_HEADERS:
            fwd_headers[k] = v
    fwd_headers["host"] = "app.stealthwriter.ai"
    fwd_headers["origin"] = TARGET
    fwd_headers["referer"] = f"{TARGET}/dashboard"

    # Send cookies as a raw Cookie header so domain-matching is bypassed entirely
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

    content = resp.content
    media_type = resp.headers.get("content-type", "application/octet-stream")

    if "text/html" in media_type:
        content = _rewrite_html(content.decode("utf-8", errors="replace"), url).encode("utf-8")

    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in _DROP_RESPONSE_HEADERS
    }
    # Rewrite redirect locations so they stay on our proxy
    if "location" in resp_headers:
        resp_headers["location"] = resp_headers["location"].replace(TARGET, "")

    response = Response(
        content=content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=media_type,
    )

    # Cache successful static asset responses
    if request.method == "GET" and _is_static(path) and resp.status_code == 200:
        _cache[url] = (content, resp.status_code, dict(resp_headers), media_type, time.time() + _CACHE_TTL)

    return response
