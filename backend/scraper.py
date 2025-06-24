# backend/scraper.py
"""
Reusable Playwright helper for:
1.  logging in (once, cached cookies)
2.  scrolling a target account's follower list
3.  pulling bios for each follower
"""

import asyncio, time, random
from pathlib import Path
from typing import List, Dict
from playwright.async_api import Browser, TimeoutError as PlayTimeout
import httpx



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
    """Open instagram.com and authenticate if necessary."""
    await page.goto("https://www.instagram.com/", timeout=probe_timeout)

    # Already logged in?
    if not await page.is_visible('input[name="username"]'):
        print("✅ Already logged in.")
        return

    # --- Log in ---
    print("🔑 Logging in…")
    await page.fill('input[name="username"]', login_user)
    await page.fill('input[name="password"]', login_pass)

    async with page.expect_navigation():
        await page.click('button[type="submit"]')

    print("🎉 Login complete.")


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
        user_agent="Mozilla/5.0 (X11; Linux x86_64)"
    )
    page = await context.new_page()
    try:
        await ensure_login(page, login_user, login_pass)

        # -- open the target followers overlay --
        await page.goto(f"https://www.instagram.com/{target}/")
        await page.screenshot(
            path=f"shots/{target}_profile.png",
            full_page=True,
        )
        print(f"📸  Saved screenshot → shots/{target}_profile.png")
        await page.click('a[href$="/followers/"]')
        await page.wait_for_selector('div[role="dialog"]', timeout=15_000)
        dialog = page.locator('div[role="dialog"]').last
        first_link = dialog.locator('a[href^="/"]').first
        await first_link.wait_for(state="attached", timeout=15_000)

        user_links = dialog.locator('a[href^="/"]')

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

        bios = []
        for handle in sorted(followers)[:max_followers]:
            try:
                bio = await get_bio(page, handle)
            except Exception as e:
                print("bio error", handle, e)
                bio = ""
            bios.append({"username": handle, "bio": bio})

        async with httpx.AsyncClient(timeout=45.0) as client:
            bio_texts = [b["bio"] for b in bios]

            try:
                print("Bio texts:", bio_texts)
                r = await client.post(
                "https://bio-classifier.onrender.com/classify",
                json={"bios": bio_texts},
                )
                r.raise_for_status()
                print("Response:", r.json())
                flags = r.json()["results"]
            except httpx.HTTPError as e:
                print("❗️Remote classify failed:", e)
                # optional fallback to local classify_profiles
                flags = [ str(i) for i, bio in enumerate(bio_texts) if bio ]

        yes_usernames = [bios[int(idx)]["username"] for idx in flags]
        yes_rows = [
        {
            "username": u,
            "url": f"https://www.instagram.com/{u}/",
        }
            for u in yes_usernames
        ]
    except Exception as e:
        # Capture the page state on failure
        await page.screenshot(path=f"shots/error_{target}.png", full_page=True)
        print(f"❌ Error during scrape: {e}. Screenshot saved to shots/error_{target}.png")
        raise
    finally:
        # Always close the context so the video is flushed to disk
        await context.close()
    return yes_rows
