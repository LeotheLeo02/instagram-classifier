# Use a Playwright-ready image from Microsoft
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory inside the container
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your entire backend code into the container
COPY . .

# Default environment settings
ENV PYTHONUNBUFFERED=1

# Command to run your FastAPI app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]