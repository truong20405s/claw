#!/usr/bin/env bash
set -e

echo "[WARP] Starting dbus service..."
mkdir -p /var/run/dbus
dbus-daemon --system --fork 2>/dev/null || true

echo "[WARP] Starting warp-svc..."
warp-svc --accept-tos &
WARP_PID=$!

sleep 3

echo "[WARP] Initializing registration & mode..."
# Accept TOS, set mode to proxy and connect
warp-cli --accept-tos registration new 2>/dev/null || true
warp-cli --accept-tos mode proxy
warp-cli --accept-tos proxy port 40000
warp-cli --accept-tos connect

# Verify connection & test actual HTTP traffic through SOCKS5 proxy
WARP_READY=false
for i in {1..30}; do
    STATUS=$(warp-cli --accept-tos status 2>/dev/null || echo "")
    echo "[WARP] Attempt $i - Status: $STATUS"

    # Test curl through local SOCKS5 proxy to verify it can resolve and route
    if curl -s -m 5 --socks5 127.0.0.1:40000 https://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -qi "warp=on"; then
        echo "[WARP] SOCKS5 proxy is verified and ROUTING traffic successfully!"
        WARP_READY=true
        break
    elif echo "$STATUS" | grep -qi "Connected"; then
        # Fallback check if cloudflare trace is slow
        echo "[WARP] WARP is Connected, checking port 40000..."
        if curl -s -m 3 --socks5 127.0.0.1:40000 https://httpbin.org/ip >/dev/null 2>&1 || curl -s -m 3 --socks5 127.0.0.1:40000 https://1.1.1.1 >/dev/null 2>&1; then
            echo "[WARP] SOCKS5 proxy on port 40000 is active!"
            WARP_READY=true
            break
        fi
    fi
    sleep 2
done

if [ "$WARP_READY" = "false" ]; then
    echo "[WARP] WARP daemon did not connect in time. Unsetting PROXY_SERVER fallback..."
    export PROXY_SERVER=""
fi

PROXY_ARG=()
if [ -n "$PROXY_SERVER" ]; then
    PROXY_ARG=(--proxy-server "$PROXY_SERVER")
fi

echo "[APP] Launching Python application with PROXY: ${PROXY_SERVER:-none}..."
exec python app.py --headless "${PROXY_ARG[@]}" "$@"
