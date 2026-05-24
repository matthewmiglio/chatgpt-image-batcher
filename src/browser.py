import os

from playwright.async_api import async_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROFILE_DIR = os.path.join(ROOT, "data", "browser_profile")


async def launch_browser(headless: bool = False):
    os.makedirs(PROFILE_DIR, exist_ok=True)
    pw = await async_playwright().start()
    context = await pw.chromium.launch_persistent_context(
        PROFILE_DIR,
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        accept_downloads=True,
    )
    page = context.pages[0] if context.pages else await context.new_page()
    return pw, context, page


async def check_login_status(page) -> bool:
    """Return True if a ChatGPT session is active (not on the login wall)."""
    url = page.url.lower()
    if "auth.openai.com" in url or "/auth/login" in url or "/login" in url:
        return False
    # Composer present => logged in
    try:
        await page.wait_for_selector(
            '#prompt-textarea[contenteditable="true"]', timeout=8000
        )
        return True
    except Exception:
        return False


async def login_session():
    """Open ChatGPT for an interactive login. Session is persisted to PROFILE_DIR."""
    pw, context, page = await launch_browser(headless=False)
    await page.goto("https://chatgpt.com/", wait_until="domcontentloaded")
    print("=" * 60)
    print(" Log into ChatGPT in the opened browser window.")
    print(" When you can see the prompt composer, CLOSE the window.")
    print(" Your session will be saved to:")
    print(f"   {PROFILE_DIR}")
    print("=" * 60)
    try:
        await context.pages[0].wait_for_event("close", timeout=0)
    except Exception:
        pass
    try:
        await context.close()
    except Exception:
        pass
    await pw.stop()
