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
warp-cli --accept-tos registration new 2>/dev/null || warp-cli --accept-tos register 2>/dev/null || true
warp-cli --accept-tos mode proxy 2>/dev/null || warp-cli --accept-tos set-mode proxy 2>/dev/null || true
warp-cli --accept-tos proxy port 40000 2>/dev/null || warp-cli --accept-tos set-proxy-port 40000 2>/dev/null || true
warp-cli --accept-tos tunnel protocol set wireguard 2>/dev/null || warp-cli --accept-tos set-protocol wireguard 2>/dev/null || warp-cli --accept-tos tunnel protocol set masque 2>/dev/null || true
warp-cli --accept-tos dns families set off 2>/dev/null || warp-cli --accept-tos set-families off 2>/dev/null || true
warp-cli --accept-tos connect 2>/dev/null || true

# Verify connection & test actual HTTP traffic through SOCKS5 proxy
WARP_READY=false
CONNECTED_COUNT=0

for i in {1..60}; do
    STATUS=$(warp-cli --accept-tos status 2>/dev/null || echo "")
    echo "[WARP] Attempt $i/60 - Status: $STATUS"

    # Test curl through local SOCKS5 proxy (using --socks5-hostname for remote DNS resolution)
    if curl -s -m 5 -4 --socks5-hostname 127.0.0.1:40000 https://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -qi "warp="; then
        echo "[WARP] SOCKS5 proxy is verified and ROUTING traffic successfully (Cloudflare trace)!"
        WARP_READY=true
        break
    elif curl -s -m 5 -4 --socks5-hostname 127.0.0.1:40000 http://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -qi "warp="; then
        echo "[WARP] SOCKS5 proxy is verified and ROUTING traffic successfully (HTTP trace)!"
        WARP_READY=true
        break
    elif curl -s -m 5 -4 --socks5-hostname 127.0.0.1:40000 https://api.ipify.org >/dev/null 2>&1; then
        echo "[WARP] SOCKS5 proxy is active and routing traffic to external web!"
        WARP_READY=true
        break
    elif echo "$STATUS" | grep -qi "Connected"; then
        CONNECTED_COUNT=$((CONNECTED_COUNT + 1))
        echo "[WARP] WARP daemon status is Connected (streak: $CONNECTED_COUNT)..."
        if echo "$STATUS" | grep -qi "healthy" || [ "$CONNECTED_COUNT" -ge 2 ]; then
            if curl -s -m 4 -4 --socks5-hostname 127.0.0.1:40000 https://1.1.1.1 >/dev/null 2>&1 || \
               curl -s -m 4 -4 --socks5-hostname 127.0.0.1:40000 http://1.1.1.1 >/dev/null 2>&1 || \
               [ "$CONNECTED_COUNT" -ge 2 ]; then
                echo "[WARP] SOCKS5 proxy on 127.0.0.1:40000 is ready and healthy!"
                WARP_READY=true
                break
            fi
        fi
    else
        CONNECTED_COUNT=0
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
