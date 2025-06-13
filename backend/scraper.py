# backend/scraper.py
"""
Reusable Playwright helper for:
1.  logging in (once, cached cookies)
2.  scrolling a target account's follower list
3.  pulling bios for each follower
"""

import asyncio, time, json
from pathlib import Path
from typing import List, Dict
import re
from playwright.async_api import Browser, BrowserContext, TimeoutError as PlayTimeout

# ---------- simple BIO extractor ---------------------------------
async def get_bio(page, username: str) -> str:
    """Return the profile bio (may be empty)."""
    await page.goto(f"https://www.instagram.com/{username}/", timeout=30_000)
    try:
        desc = await page.get_attribute("head meta[name='description']", "content")
        if desc and " on Instagram: " in desc:
            return desc.split(" on Instagram: ")[1].strip().strip('"')
    except Exception:
        pass
    return ""


async def ensure_login(
    page,
    login_user: str,
    login_pass: str,
    probe_timeout: int = 8_000,
) -> None:
    state_path = Path(f"{login_user}_state.json")

    # 1️⃣ probe with the same page
    try:
        await page.goto("https://www.instagram.com/", timeout=probe_timeout)
    except PlayTimeout:
        pass

    if "/accounts/login" not in page.url:
        return  # already logged in

    # 2️⃣ perform login on the same page
    print("🔑 Logging in…")
    await page.goto("https://www.instagram.com/accounts/login/")
    await page.fill('[name="username"]', login_user)
    await page.fill('[name="password"]', login_pass)
    await page.click('button[type="submit"]')
    try:
        await page.wait_for_selector('text=/Not now/i', timeout=8_000)
        await page.click('text=/Not now/i')
    except PlayTimeout:
        pass

    # 3️⃣ save cookies into context’s storage
    #    but we still need the context, so grab it back:
    await page.context.storage_state(path=state_path)

# ---------- main scrape helper -----------------------------------
async def scrape_followers(
    browser: Browser,
    login_user: str,
    login_pass: str,
    target: str,
    max_followers: int = 100,
    scroll_seconds: int = 120,
) -> List[Dict]:
    """
    Reuses a running `browser` (passed from FastAPI lifespan),
    logs in with given creds (if not cached), scrolls follower list,
    returns a list of {'username': str, 'bio': str}.
    """
    state_path = Path(f"{login_user}_state.json")
    context = await browser.new_context(
        storage_state=state_path if state_path.exists() else None,
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (X11; Linux x86_64)",
    )
    page = await context.new_page()
    await ensure_login(page, login_user, login_pass)

    # -- open the target followers overlay --
    await page.goto(f"https://www.instagram.com/{target}/")
    await page.click('a[href$="/followers/"]')
    await page.wait_for_selector('div[role="dialog"]', timeout=15_000)
    dialog = page.locator('div[role="dialog"]').last
    first_link = dialog.locator('a[href^="/"]').first
    await first_link.wait_for(state="attached", timeout=15_000)

    user_links = dialog.locator('a[href^="/"]')
    scroll_box = await dialog.evaluate_handle(
        "d => [...d.querySelectorAll('div')].find(x => ['auto','scroll'].includes(getComputedStyle(x).overflowY)) || d"
    )

    followers = set()
    start = time.time()

    while (time.time() - start) < scroll_seconds and len(followers) < max_followers:
        for t in await user_links.all_inner_texts():
            if t.strip():
                followers.add(t.strip())
        if len(followers) >= max_followers:
            break
        # scroll
        count_links = await user_links.count()
        if count_links:
            await user_links.nth(count_links - 1).scroll_into_view_if_needed()
        await asyncio.sleep(1)

    print(f"Collected {len(followers)} handles; now fetching bios…")

    results = []
    for handle in sorted(followers)[:max_followers]:
        try:
            bio = await get_bio(page, handle)
        except Exception as e:
            print("bio error", handle, e)
            bio = ""
        results.append({"username": handle, "bio": bio})

    await context.close()
    return results
