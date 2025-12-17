FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Install Chrome/Chromedriver and minimal deps for Selenium headless
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatspi2.0-0 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnss3 \
        libxcomposite1 \
        libxrandr2 \
        libxss1 && \
    rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
