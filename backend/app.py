from fastapi import FastAPI
from pydantic import BaseModel
import os
from scraper import scrape_followers

from playwright.async_api import async_playwright

async def lifespan(app: FastAPI):
    # 1) start Playwright once
    pw = await async_playwright().start()
    # 2) launch a single browser instance (headless in prod)
    browser = await pw.chromium.launch(headless=True)   # True on server
    # 3) stash them so routes can reuse
    app.state.playwright = pw
    app.state.browser = browser
    yield                                   # --- app runs here ---
    # 4) graceful shutdown
    await browser.close()
    await pw.stop()

app = FastAPI(lifespan=lifespan)

class Req(BaseModel):
    target: str
    max_followers: int

@app.post("/classify")
async def classify(req: Req):
    print("🔍 Received request:", req.dict())
    print("✅ Starting scrape with:", os.getenv("IG_USER"))
    bios = await scrape_followers(
        browser=app.state.browser,
        login_user=os.getenv("IG_USER"),
        login_pass=os.getenv("IG_PASS"),
        target=req.target,
        max_followers=req.max_followers,
    )
    return {"results": bios}