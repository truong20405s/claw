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

# Verify connection
WARP_READY=false
for i in {1..25}; do
    STATUS=$(warp-cli --accept-tos status 2>/dev/null || echo "")
    echo "[WARP] Attempt $i - Status: $STATUS"
    if echo "$STATUS" | grep -qi "Connected"; then
        echo "[WARP] WARP is successfully CONNECTED!"
        WARP_READY=true
        break
    fi
    sleep 2
done

if [ "$WARP_READY" = "false" ]; then
    echo "[WARP] WARP daemon did not connect in time. Unsetting PROXY_SERVER fallback..."
    export PROXY_SERVER=""
fi

echo "[APP] Launching Python application..."
exec python app.py --headless "$@"
