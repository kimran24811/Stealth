from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import tempfile
import uuid
import subprocess
import json
import signal

# Fix: Go up 3 levels from src/auth/selenium_login.py to get to project root  
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COOKIES_FILE = os.path.join(PROJECT_ROOT, "manual_cookies.json")

def manual_login_and_capture_cookies():
    """
    Opens a browser window for manual login and captures cookies after successful login
    """
    print("🚀 Starting manual login process...")

    options = webdriver.ChromeOptions()
    temp_dir = tempfile.gettempdir()
    unique_id = str(uuid.uuid4())
    user_data_dir = os.path.join(temp_dir, f"chrome_manual_{unique_id}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--window-size=1200,800")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")

    use_headless = os.getenv("SELENIUM_HEADLESS", "false").lower() == "true"
    if use_headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get("https://app.stealthwriter.ai/auth/sign-in")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "email"))
        )

        print("\n" + "="*70)
        print("🎯 MANUAL LOGIN REQUIRED")
        print("="*70)
        print("1. Enter your email and password in the browser")
        print("2. Complete the Cloudflare Turnstile challenge")
        print("3. Click the Login button")
        print("4. Wait until you reach the dashboard/main page")
        print("5. Then press Enter in this terminal")
        print("="*70)

        input("\n⌨️  Press Enter after login completion: ")

        current_url = driver.current_url
        page_source = driver.page_source.lower()

        login_indicators = [
            "dashboard" in current_url,
            "app.stealthwriter.ai" in current_url and "sign-in" not in current_url,
            "dashboard" in page_source,
            "welcome" in page_source,
            "logout" in page_source,
            current_url != "https://app.stealthwriter.ai/auth/sign-in"
        ]

        if any(login_indicators):
            cookies = driver.get_cookies()
            valid_cookies = [cookie for cookie in cookies if cookie.get('name') and cookie.get('value')]
            cookies_data = {
                "timestamp": time.time(),
                "url": current_url,
                "cookies": valid_cookies
            }
            # Fix: Use COOKIES_FILE instead of hardcoded path
            with open(COOKIES_FILE, "w") as f:
                json.dump(cookies_data, f, indent=2)
            print(f"💾 Cookies saved to {COOKIES_FILE}")
            return valid_cookies
        else:
            print(f"❌ Login not detected. Current URL: {current_url}")
            raise Exception("Login verification failed - not on dashboard page")
    except Exception as e:
        raise Exception(f"Manual login failed: {str(e)}")
    finally:
        if driver:
            time.sleep(2)
            try:
                driver.quit()
            except Exception:
                pass
        try:
            import shutil
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception:
            pass

def load_manual_cookies():
    """
    Load cookies from manual_cookies.json file
    """
    try:
        if not os.path.exists(COOKIES_FILE):
            return None
        with open(COOKIES_FILE, "r") as f:  # Fix: Use COOKIES_FILE instead of cookies_file
            cookies_data = json.load(f)
        cookie_age = time.time() - cookies_data["timestamp"]
        max_age = 86400  # 24 hours
        if cookie_age > max_age:
            print(f"⏰ Manual cookies are {cookie_age/3600:.1f} hours old (max {max_age/3600} hours)")
            return None
        cookies = cookies_data["cookies"]
        print(f"✅ Loaded {len(cookies)} manual cookies (age: {cookie_age/3600:.1f} hours)")
        return cookies
    except Exception as e:
        print(f"❌ Failed to load manual cookies: {e}")
        return None
