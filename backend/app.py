from fastapi import FastAPI
from pydantic import BaseModel
import os
from scraper import scrape_followers
from playwright.async_api import async_playwright
from fastapi.responses import StreamingResponse, FileResponse
from pathlib import Path

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


@app.get("/debug/screenshot")
async def debug_shot(filename: str = "last.png"):
    shot_path = Path("shots") / filename
    if not shot_path.exists():
        return {"error": "file not found"}
    return StreamingResponse(
        shot_path.open("rb"),
        media_type="image/png"
    )

@app.get("/debug/video")
async def debug_video(filename: str):
    path = Path("videos") / filename
    if not path.exists():
        return {"error": f"{filename} not found"}
    return FileResponse(path, media_type="video/webm")