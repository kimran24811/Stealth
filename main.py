import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn

import httpx
from proxy import proxy_request
from session import check_session, save_cookies, get_cookies

app = FastAPI(title="StealthWriter Proxy", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/session-status")
async def session_status():
    return check_session()


@app.get("/debug-auth")
async def debug_auth():
    """Check if our cookies are accepted by StealthWriter's auth system."""
    cookies = get_cookies()
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "cookie": cookie_header,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        r = await client.get("https://app.stealthwriter.ai/api/auth/get-session", headers=headers)
    return {"status": r.status_code, "body": r.text[:1000]}


@app.post("/update-cookies")
async def update_cookies(request: Request):
    """
    Accept cookies as a JSON body in one of two formats:
      {"cookies": {"name": "value", ...}}          <- dict
      {"cookies": [{"name": "...", "value": "..."}, ...]}  <- browser export list
    """
    data = await request.json()
    cookies = data.get("cookies")
    if not cookies:
        return JSONResponse({"error": "Missing 'cookies' field."}, status_code=400)
    save_cookies(cookies)
    return {"status": "ok", "message": "Cookies saved."}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def catch_all(path: str, request: Request):
    return await proxy_request(path, request)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False,
    )
