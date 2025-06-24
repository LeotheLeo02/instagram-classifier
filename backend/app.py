from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright
from .scraper import scrape_followers

async def lifespan(app: FastAPI):
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)
    app.state.playwright = pw
    app.state.browser = browser
    yield
    await browser.close()
    await pw.stop()

app = FastAPI(lifespan=lifespan)

# allow the Vite dev-server (5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ClassifyRequest(BaseModel):
    login_user: str
    login_pass: str
    target: str
    max_followers: int = 50

class YesRow(BaseModel):
    username: str
    url: str

class ClassifyResponse(BaseModel):
    count: int
    results: list[YesRow]

@app.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    yes_usernames = await scrape_followers(
        browser=app.state.browser,
        login_user=req.login_user,
        login_pass=req.login_pass,
        target=req.target,
        max_followers=req.max_followers,
    )
    return {"count": len(yes_usernames), "results": yes_usernames}