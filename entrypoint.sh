#!/usr/bin/env bash
set -e

echo "[WARP] Starting dbus service..."
mkdir -p /var/run/dbus
dbus-daemon --system --fork 2>/dev/null || true

echo "[WARP] Starting Cloudflare WARP daemon..."
warp-svc --accept-tos &
WARP_PID=$!

echo "[WARP] Waiting for warp-svc to initialize..."
for i in {1..15}; do
    if warp-cli --accept-tos status 2>/dev/null | grep -qE "RegistrationMissing|Disconnected|Connected"; then
        break
    fi
    sleep 1
done

echo "[WARP] Registering and setting proxy mode..."
warp-cli --accept-tos registration new 2>/dev/null || true
warp-cli --accept-tos mode proxy
warp-cli --accept-tos proxy port 40000
warp-cli --accept-tos connect

echo "[WARP] Verifying WARP connection..."
for i in {1..20}; do
    STATUS=$(warp-cli --accept-tos status 2>/dev/null || echo "error")
    echo "[WARP] Current status: $STATUS"
    if echo "$STATUS" | grep -qi "Connected"; then
        echo "[WARP] Connected successfully! Traffic will be routed through Cloudflare WARP."
        break
    fi
    sleep 1
done

echo "[APP] Launching application..."
exec python app.py --headless "$@"
