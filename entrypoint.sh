#!/usr/bin/env bash
set -e

echo "[WARP] Starting dbus service..."
mkdir -p /var/run/dbus
dbus-daemon --system --fork 2>/dev/null || true

echo "[WARP] Starting warp-svc..."
warp-svc --accept-tos >/tmp/warp-svc.log 2>&1 &
WARP_PID=$!

sleep 3

echo "[WARP] Initializing registration & mode..."
# Accept TOS, set mode to proxy, disable IPv6/fallback to IPv4 and connect
warp-cli --accept-tos registration new 2>/dev/null || true
warp-cli --accept-tos mode proxy
warp-cli --accept-tos proxy port 40000
warp-cli --accept-tos tunnel protocol wireguard 2>/dev/null || warp-cli --accept-tos tunnel protocol masque 2>/dev/null || true
warp-cli --accept-tos connect

# Verify connection & test actual HTTP traffic through SOCKS5 proxy
WARP_READY=false
for i in {1..60}; do
    STATUS=$(warp-cli --accept-tos status 2>/dev/null || echo "")
    echo "[WARP] Attempt $i/60 - Status: $STATUS"

    if echo "$STATUS" | grep -qi "Connected"; then
        echo "[WARP] Status is Connected! Verifying SOCKS5 proxy on 127.0.0.1:40000..."
        # Give warp a moment to bind socks port if just connected
        sleep 1
        if curl -s -m 5 --socks5 127.0.0.1:40000 https://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -qi "warp="; then
            echo "[WARP] SOCKS5 proxy is verified and ROUTING traffic successfully!"
            WARP_READY=true
            break
        elif curl -s -m 4 --socks5 127.0.0.1:40000 https://1.1.1.1 >/dev/null 2>&1 || curl -s -m 4 --socks5 127.0.0.1:40000 https://httpbin.org/ip >/dev/null 2>&1; then
            echo "[WARP] SOCKS5 proxy is active and responding!"
            WARP_READY=true
            break
        fi
    elif curl -s -m 4 --socks5 127.0.0.1:40000 https://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -qi "warp="; then
        echo "[WARP] SOCKS5 proxy is verified and ROUTING traffic successfully!"
        WARP_READY=true
        break
    fi
    sleep 2
done

if [ "$WARP_READY" = "false" ]; then
    echo "[WARP] WARP daemon did not connect in time. Printing recent warp-svc logs:"
    tail -n 25 /tmp/warp-svc.log 2>/dev/null || true
    echo "[WARP] Unsetting PROXY_SERVER fallback..."
    export PROXY_SERVER=""
fi

PROXY_ARG=()
if [ -n "$PROXY_SERVER" ]; then
    PROXY_ARG=(--proxy-server "$PROXY_SERVER")
fi

echo "[APP] Launching Python application with PROXY: ${PROXY_SERVER:-none}..."
exec python app.py --headless "${PROXY_ARG[@]}" "$@"
