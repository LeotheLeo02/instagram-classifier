# Dockerfile (at project root)

FROM python:3.9-slim

# 1) where we live
WORKDIR /app

# 2) install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) copy your code
COPY backend/ backend/

# 4) tell uvicorn to import backend.app:app
ENV PORT 8000
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]