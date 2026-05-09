from fastapi import APIRouter, Request, Response, HTTPException
from auth.session import get_authenticated_client, force_refresh_session, get_session_status
from auth.selenium_login import manual_login_and_capture_cookies, load_manual_cookies
import os
import asyncio
import time
import json
import hashlib
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import subprocess
import tempfile
import shutil

router = APIRouter()

# Cache for HTML responses
_html_cache = {}
_cache_lock = asyncio.Lock()
_cache_timeout = 300  # 5 minutes

def get_content_type(url: str) -> str:
    """Determine content type based on file extension"""
    if url.endswith('.css'):
        return 'text/css'
    elif url.endswith('.js'):
        return 'application/javascript'
    elif url.endswith('.woff') or url.endswith('.woff2'):
        return 'font/woff2'
    elif url.endswith('.ttf'):
        return 'font/ttf'
    elif url.endswith('.svg'):
        return 'image/svg+xml'
    elif url.endswith('.png'):
        return 'image/png'
    elif url.endswith('.jpg') or url.endswith('.jpeg'):
        return 'image/jpeg'
    elif url.endswith('.gif'):
        return 'image/gif'
    elif url.endswith('.ico'):
        return 'image/x-icon'
    else:
        return 'text/html'

def clean_headers(headers: dict) -> dict:
    """Clean and filter response headers"""
    filtered_headers = {}
    skip_headers = {
        "content-encoding", "transfer-encoding", "connection", 
        "content-length", "server", "x-frame-options", "cf-ray"
    }
    
    for k, v in headers.items():
        if k.lower() in skip_headers:
            continue
        
        if isinstance(v, str):
            clean_value = v.replace('\n', ' ').replace('\r', ' ').strip()
            if clean_value and len(clean_value) < 8192:
                filtered_headers[k] = clean_value
    
    return filtered_headers

def handle_403_response(target_url: str) -> Response:
    """Handle Cloudflare 403 responses with helpful error page"""
    error_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Session Refresh Required</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f8fafc; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .error {{ background: #ffebee; padding: 20px; border-radius: 8px; border-left: 4px solid #f44336; margin: 15px 0; }}
            .solution {{ background: #e8f5e8; padding: 20px; border-radius: 8px; border-left: 4px solid #4caf50; margin: 15px 0; }}
            .code {{ background: #f5f5f5; padding: 10px; border-radius: 4px; font-family: monospace; margin: 10px 0; }}
            button {{ background: #007bff; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-size: 16px; margin: 10px 5px; }}
            button:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Cloudflare Protection Detected</h1>
            
            <div class="error">
                <h3>❌ Access Blocked</h3>
                <p><strong>The target website is blocking automated access.</strong></p>
                <p>Please update your cookies manually or use the refresh endpoint.</p>
                <p><strong>Target URL:</strong> {target_url}</p>
            </div>
            
            <div class="solution">
                <h3>🔧 Solutions</h3>
                <button onclick="refreshSession()">🔄 Refresh Session</button>
                <button onclick="updateCookies()">🍪 Update Cookies</button>
                <button onclick="checkStatus()">📊 Check Status</button>
            </div>
            
            <div id="result" style="margin-top: 20px;"></div>
        </div>
        
        <script>
            async function refreshSession() {{
                const result = document.getElementById('result');
                result.innerHTML = '<p>🔄 Refreshing session...</p>';
                
                try {{
                    const response = await fetch('/refresh-session', {{ method: 'POST' }});
                    const data = await response.json();
                    
                    if (data.status === 'success') {{
                        result.innerHTML = '<div class="solution"><p>✅ Session refreshed! Try again.</p></div>';
                        setTimeout(() => window.location.reload(), 2000);
                    }} else {{
                        result.innerHTML = '<div class="error"><p>❌ Refresh failed: ' + data.message + '</p></div>';
                    }}
                }} catch (e) {{
                    result.innerHTML = '<div class="error"><p>❌ Error: ' + e.message + '</p></div>';
                }}
            }}
            
            async function checkStatus() {{
                const result = document.getElementById('result');
                result.innerHTML = '<p>🔍 Checking status...</p>';
                
                try {{
                    const response = await fetch('/session-status');
                    const data = await response.json();
                    result.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                }} catch (e) {{
                    result.innerHTML = '<div class="error"><p>❌ Error: ' + e.message + '</p></div>';
                }}
            }}
            
            function updateCookies() {{
                alert('Please update the manual_cookies.json file with fresh cookies from your browser, then refresh the session.');
            }}
        </script>
    </body>
    </html>
    """
    return Response(content=error_html, status_code=403, headers={"Content-Type": "text/html"})

async def get_cached_html(url: str) -> Optional[str]:
    """Check if we have cached HTML for this URL"""
    async with _cache_lock:
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key in _html_cache:
            cached_data = _html_cache[cache_key]
            if time.time() - cached_data['timestamp'] < _cache_timeout:
                print(f"📋 Cache hit for: {url}")
                return cached_data['html']
            else:
                # Remove expired cache
                del _html_cache[cache_key]
        return None

async def cache_html(url: str, html: str):
    """Cache HTML response"""
    async with _cache_lock:
        cache_key = hashlib.md5(url.encode()).hexdigest()
        _html_cache[cache_key] = {
            'html': html,
            'timestamp': time.time()
        }
        print(f"💾 Cached response for: {url}")

def setup_chrome_for_ec2():
    """Setup Chrome options optimized for EC2 Linux environment"""
    options = Options()
    
    # Essential headless options for EC2
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    
    # Memory and performance optimizations
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=2048")
    options.add_argument("--aggressive-cache-discard")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    
    # Disable unnecessary features
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--disable-javascript")  # We don't need JS for basic HTML
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees")
    options.add_argument("--disable-ipc-flooding-protection")
    
    # Network optimizations
    options.add_argument("--aggressive-cache-discard")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    
    # Window size
    options.add_argument("--window-size=1280,720")
    
    # User agent
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    # Disable automation detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Create temp directory for user data
    temp_dir = tempfile.mkdtemp(prefix="chrome_", suffix="_proxy")
    options.add_argument(f"--user-data-dir={temp_dir}")
    
    return options, temp_dir

def fetch_html_with_selenium(url: str, cookies: list) -> str:
    """Use Selenium to fetch HTML content - OPTIMIZED FOR EC2"""
    options, temp_dir = setup_chrome_for_ec2()
    
    # Try to find Chrome binary
    chrome_binary = None
    possible_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/opt/google/chrome/chrome"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            chrome_binary = path
            break
    
    if chrome_binary:
        options.binary_location = chrome_binary
        print(f"🔍 Using Chrome binary: {chrome_binary}")
    
    driver = None
    try:
        # Create service with minimal logging
        service = Service(log_level=3)  # Only fatal errors
        
        # Reduced timeouts for faster failure
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(15)  # Reduced from 30
        driver.implicitly_wait(5)  # Reduced from 10
        
        print(f"🌐 Loading base URL...")
        driver.get("https://app.stealthwriter.ai/")
        
        # Quick cookie addition
        print(f"🍪 Adding {len(cookies)} cookies...")
        for cookie in cookies[:10]:  # Limit to first 10 cookies
            try:
                cookie_dict = {
                    "name": cookie.get("name"),
                    "value": cookie.get("value"),
                    "domain": cookie.get("domain", "app.stealthwriter.ai"),
                    "path": cookie.get("path", "/")
                }
                driver.add_cookie(cookie_dict)
            except Exception as e:
                print(f"⚠️ Cookie add failed: {e}")
                continue
                
        print(f"🎯 Navigating to target: {url}")
        driver.get(url)
        
        # Quick wait - no fancy detection
        print("⏳ Waiting for page load...")
        time.sleep(8)  # Simple wait instead of complex detection
        
        html = driver.page_source
        print(f"📄 Retrieved HTML ({len(html)} characters)")
        
        # Basic validation
        if len(html) < 1000:
            raise Exception(f"HTML too short ({len(html)} chars), likely failed")
            
        return html
        
    except Exception as e:
        print(f"❌ Selenium error: {str(e)}")
        raise Exception(f"Selenium fetch failed: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        # Cleanup temp directory
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_request(path: str, request: Request):
    """Main proxy endpoint with improved error handling"""
    try:
        # Check session status
        session_status = await get_session_status()
        cookie_status = session_status.get("cookie_status", {})
        
        if not cookie_status.get("exists") or cookie_status.get("expired", True):
            return handle_403_response("Session unavailable")

        # Handle root path
        if path == "" or path == "/":
            path = "dashboard"
        
        target_url = os.getenv("TARGET_URL").rstrip("/") + "/" + path
        
        # Add query parameters
        if request.query_params:
            query_string = str(request.query_params)
            target_url += f"?{query_string}"

        content_type = get_content_type(target_url)
        
        # For HTML pages: Try cache first, then HTTPX, fallback gracefully
        if content_type == "text/html":
            
            # 1. Check cache first
            cached_html = await get_cached_html(target_url)
            if cached_html:
                return Response(
                    content=cached_html,
                    status_code=200,
                    headers={
                        "Content-Type": "text/html",
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": "no-cache"
                    }
                )
            
            # 2. Try HTTPX first (faster and more reliable)
            try:
                client = await get_authenticated_client()
                headers = {
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Referer": "https://app.stealthwriter.ai/dashboard",
                    "Origin": "https://app.stealthwriter.ai",
                    "Sec-Fetch-Site": "same-origin",
                    "DNT": "1"
                }
                
                body = await request.body()
                response = await client.request(
                    request.method,
                    target_url,
                    headers=headers,
                    content=body,
                    params=request.query_params,
                    timeout=15  # Reasonable timeout
                )
                
                # If HTTPX succeeds and content looks good
                if (response.status_code == 200 and 
                    len(response.text) > 1000 and
                    "Verifying you are human" not in response.text and
                    "Cloudflare" not in response.text):
                    
                    print(f"⚡ HTTPX success for: {target_url}")
                    await cache_html(target_url, response.text)
                    return Response(
                        content=response.text,
                        status_code=200,
                        headers={
                            "Content-Type": "text/html",
                            "Access-Control-Allow-Origin": "*",
                            "Cache-Control": "no-cache"
                        }
                    )
                else:
                    print(f"🔄 HTTPX got challenge/error, status: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠️ HTTPX failed: {str(e)}")
            
            # 3. Try Selenium as last resort (but with better error handling)
            try:
                cookies = cookie_status.get("cookies", [])
                print(f"🤖 Attempting Selenium for: {target_url}")
                
                # Run in executor with timeout
                html = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, fetch_html_with_selenium, target_url, cookies
                    ),
                    timeout=45  # 45 second timeout for entire operation
                )
                
                await cache_html(target_url, html)
                return Response(
                    content=html,
                    status_code=200,
                    headers={
                        "Content-Type": "text/html",
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": "no-cache"
                    }
                )
            except asyncio.TimeoutError:
                print(f"❌ Selenium timeout for: {target_url}")
                return handle_403_response(target_url)
            except Exception as e:
                print(f"❌ Selenium fetch failed: {str(e)}")
                return handle_403_response(target_url)
        
        # For non-HTML assets: Use HTTPX only
        else:
            client = await get_authenticated_client()
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://app.stealthwriter.ai/dashboard",
                "Origin": "https://app.stealthwriter.ai",
                "Sec-Fetch-Site": "same-origin",
                "DNT": "1"
            }
            
            # Set Accept header based on content type
            if content_type == 'text/css':
                headers["Accept"] = "text/css,*/*;q=0.1"
            elif content_type == 'application/javascript':
                headers["Accept"] = "*/*"
            elif content_type.startswith('image/'):
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
            
            filtered_headers = clean_headers(response.headers)
            filtered_headers.update({
                "Content-Type": content_type,
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Cache-Control": "public, max-age=3600"
            })
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=filtered_headers
            )
            
    except Exception as e:
        print(f"❌ Proxy error: {str(e)}")
        return handle_403_response(f"Proxy error: {str(e)}")

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
        # Clear cache when refreshing session
        async with _cache_lock:
            _html_cache.clear()
        await force_refresh_session()
        return {"status": "success", "message": "Session refreshed successfully"}
    except Exception as e:
        return {"status": "error", "message": f"Session refresh failed: {str(e)}"}

@router.post("/clear-cache")
async def clear_cache():
    """Clear HTML cache"""
    try:
        async with _cache_lock:
            cache_count = len(_html_cache)
            _html_cache.clear()
        return {"status": "success", "message": f"Cleared {cache_count} cached pages"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/update-cookies")
async def update_cookies_endpoint(request: Request):
    """Update cookies via API"""
    try:
        body = await request.json()
        if "cookies" not in body:
            raise HTTPException(status_code=400, detail="Missing 'cookies' in request body")
        
        cookies_data = {
            "timestamp": time.time(),
            "url": "https://app.stealthwriter.ai/dashboard",
            "cookies": body["cookies"]
        }
        
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        COOKIES_FILE_PATH = os.path.join(PROJECT_ROOT, "manual_cookies.json")
        
        with open(COOKIES_FILE_PATH, "w") as f:
            json.dump(cookies_data, f, indent=2)
        
        # Clear cache when updating cookies
        async with _cache_lock:
            _html_cache.clear()
        await force_refresh_session()
        
        return {
            "status": "success",
            "message": f"Updated {len(body['cookies'])} cookies and refreshed session",
            "cookie_count": len(body["cookies"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update cookies: {str(e)}")
