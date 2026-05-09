from fastapi import APIRouter, Request, Response, HTTPException
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
import os
import asyncio
import time
import json
import hashlib
from typing import Optional

router = APIRouter()

# Cache for responses
_response_cache = {}
_cache_lock = asyncio.Lock()
_cache_timeout = 600  # 10 minutes

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def simple_proxy_request(path: str, request: Request):
    """Simplified proxy that relies only on HTTPX with good cookies"""
    try:
        # Check session status
        session_status = await get_session_status()
        cookie_status = session_status.get("cookie_status", {})
        
        if not cookie_status.get("exists") or cookie_status.get("expired", True):
            return Response(
                content=f"""
                <html><body>
                <h1>🔄 Session Unavailable</h1>
                <p>Error: {cookie_status.get('error', 'No valid cookies')}</p>
                <p><a href="/session-status">Check Status</a> | <a href="/refresh-session">Refresh</a></p>
                </body></html>
                """,
                status_code=401,
                headers={"Content-Type": "text/html"}
            )

        # Handle root path
        if path == "" or path == "/":
            path = "dashboard"
        
        target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
        
        # Add query parameters
        if request.query_params:
            query_string = str(request.query_params)
            target_url += f"?{query_string}"

        # Check cache for GET requests
        cache_key = f"{request.method}:{target_url}"
        if request.method == "GET":
            async with _cache_lock:
                if cache_key in _response_cache:
                    cached = _response_cache[cache_key]
                    if time.time() - cached['timestamp'] < _cache_timeout:
                        print(f"📋 Cache hit: {target_url}")
                        return Response(
                            content=cached['content'],
                            status_code=cached['status_code'],
                            headers=cached['headers']
                        )

        # Make request with authenticated client
        client = await get_authenticated_client()
        
        # Enhanced headers to look more like a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Referer": "https://app.stealthwriter.ai/dashboard",
        }
        
        # Adjust content type specific headers
        if path.endswith('.css'):
            headers["Accept"] = "text/css,*/*;q=0.1"
        elif path.endswith('.js'):
            headers["Accept"] = "*/*"
        elif any(path.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico']):
            headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"

        body = await request.body()
        
        response = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
            params=request.query_params,
            timeout=30
        )
        
        # Determine content type
        content_type = response.headers.get("content-type", "text/html")
        if path.endswith('.css'):
            content_type = 'text/css'
        elif path.endswith('.js'):
            content_type = 'application/javascript'
        elif path.endswith(('.png', '.jpg', '.jpeg')):
            content_type = f'image/{path.split(".")[-1]}'
        
        # Clean response headers
        response_headers = {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
        
        # Add caching for static assets
        if any(path.endswith(ext) for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2']):
            response_headers["Cache-Control"] = "public, max-age=3600"
        else:
            response_headers["Cache-Control"] = "no-cache"

        # Cache successful GET responses
        if request.method == "GET" and response.status_code == 200:
            async with _cache_lock:
                _response_cache[cache_key] = {
                    'content': response.content,
                    'status_code': response.status_code,
                    'headers': response_headers,
                    'timestamp': time.time()
                }
                # Limit cache size
                if len(_response_cache) > 100:
                    oldest_key = min(_response_cache.keys(), key=lambda k: _response_cache[k]['timestamp'])
                    del _response_cache[oldest_key]

        print(f"✅ Proxied: {request.method} {target_url} -> {response.status_code}")
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers
        )
            
    except Exception as e:
        print(f"❌ Proxy error: {str(e)}")
        return Response(
            content=f"""
            <html><body>
            <h1>🚫 Proxy Error</h1>
            <p>Failed to fetch: {target_url}</p>
            <p>Error: {str(e)}</p>
            <p><a href="/session-status">Check Session Status</a></p>
            </body></html>
            """,
            status_code=500,
            headers={"Content-Type": "text/html"}
        )

@router.get("/session-status")
async def session_status():
    """Check current session status"""
    try:
        return await get_session_status()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/refresh-session")
async def refresh_session():
    """Force refresh session"""
    try:
        async with _cache_lock:
            _response_cache.clear()
        await force_refresh_session()
        return {"status": "success", "message": "Session refreshed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Session refresh failed: {str(e)}"}
        