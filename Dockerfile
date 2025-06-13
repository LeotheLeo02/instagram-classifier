# ───────────────────────────────────────────────────────────
# Dockerfile  (repo root)
# ───────────────────────────────────────────────────────────
FROM python:3.9-slim AS base

# 1) system packages required by Playwright/Chromium
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl gnupg ca-certificates fonts-liberation libnss3 libatk1.0-0 \
        libatk-bridge2.0-0 libgtk-3-0 libx11-xcb1 libxcomposite1 libxdamage1 \
        libgbm1 libpango-1.0-0 libcups2 libxrandr2 xdg-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) Install Playwright itself + browser binaries
RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

# 4) Copy application code
COPY backend/ backend/

# (Optional) make backend a proper package
RUN touch backend/__init__.py

# 5) Environment & startup
ENV PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

ENV PYTHONPATH="/app/backend"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]