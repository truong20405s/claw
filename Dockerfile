FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/chromium \
    TZ=Asia/Bangkok \
    PROXY_SERVER=socks5://127.0.0.1:40000

# Install Chromium, WARP dependencies and networking utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    lsb-release \
    chromium \
    ca-certificates \
    dbus \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    procps \
    && curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-client.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends cloudflare-warp \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh 2>/dev/null || true

CMD ["/bin/bash", "/app/entrypoint.sh"]
