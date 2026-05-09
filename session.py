import json
from pathlib import Path

COOKIES_FILE = "manual_cookies.json"


def get_cookies() -> dict:
    """Load cookies from file, return as {name: value} dict."""
    if not Path(COOKIES_FILE).exists():
        return {}
    try:
        with open(COOKIES_FILE) as f:
            data = json.load(f)
        # Support browser-exported list format: [{name, value, ...}, ...]
        if isinstance(data, list):
            return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_cookies(cookies: dict | list):
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)


def check_session() -> dict:
    cookies = get_cookies()
    if not cookies:
        return {
            "status": "no_cookies",
            "cookie_count": 0,
            "message": "No cookies found. Add cookies via POST /update-cookies.",
        }
    return {
        "status": "active",
        "cookie_count": len(cookies),
        "message": "Session cookies are loaded.",
    }
