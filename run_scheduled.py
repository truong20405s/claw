"""
Scheduled runner for GitHub Actions.

Workflow:
1. Every 3h50m, GitHub Actions spins up this script.
2. Load state file (last_run_time, current_account_index).
3. If not enough time has passed since last run → sleep until 4h mark.
4. Run the next account in rotation.
5. Save updated state (new last_run_time, next account index).
6. Exit.

State is persisted via GitHub Actions cache or artifact between runs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import nodriver as uc

from account_rotation import run_account_session
from app_config import apply_interval_override, load_rotation_config, parse_args
from app_config import parse_proxy_pool
from account_rotation import ProxyPool

log = logging.getLogger("claw.scheduled")

STATE_FILE = Path(__file__).resolve().with_name("state.json")
INTERVAL_HOURS = 4.0
INTERVAL_SECONDS = INTERVAL_HOURS * 3600


def load_state() -> dict:
    """Load state from file. Returns default state if file doesn't exist."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            log.info(
                "Loaded state: last_run=%s, account_index=%d",
                data.get("last_run_time", "never"),
                data.get("account_index", 0),
            )
            return data
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Corrupted state file, starting fresh: %s", e)

    default = {
        "last_run_time": None,
        "account_index": 0,
        "total_runs": 0,
        "history": [],
    }
    log.info("No state file found, starting fresh.")
    return default


def save_state(state: dict) -> None:
    """Save state to file."""
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info(
        "State saved: last_run=%s, next_account_index=%d, total_runs=%d",
        state["last_run_time"],
        state["account_index"],
        state["total_runs"],
    )


def wait_until_ready(state: dict) -> None:
    """If not enough time has passed, sleep until 4h mark."""
    last_run = state.get("last_run_time")
    if last_run is None:
        log.info("First run ever — no wait needed.")
        return

    last_run_dt = datetime.fromisoformat(last_run)
    now = datetime.now(timezone.utc)
    elapsed = (now - last_run_dt).total_seconds()

    if elapsed >= INTERVAL_SECONDS:
        log.info(
            "Enough time passed (%.1fh >= %.1fh). Ready to run.",
            elapsed / 3600,
            INTERVAL_HOURS,
        )
        return

    wait_seconds = INTERVAL_SECONDS - elapsed
    wait_minutes = wait_seconds / 60
    log.info(
        "Not enough time yet (%.1fh < %.1fh). Sleeping %.1f minutes...",
        elapsed / 3600,
        INTERVAL_HOURS,
        wait_minutes,
    )
    time.sleep(wait_seconds)
    log.info("Wait complete. Ready to run.")


def get_next_account(accounts: list[dict], state: dict) -> tuple[int, dict]:
    """Get the next account in rotation."""
    index = state.get("account_index", 0) % len(accounts)
    account = accounts[index]
    log.info(
        "Selected account %d/%d: %s",
        index + 1,
        len(accounts),
        account["account"],
    )
    return index, account


async def async_main() -> None:
    args = parse_args()

    # Setup logging
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("claw.log", encoding="utf-8"),
        ],
    )

    # Auto headless on Linux without display
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        args.headless = True

    # Load config
    config_path = Path(args.config).expanduser().resolve()
    config = load_rotation_config(config_path)
    apply_interval_override(config, args.interval_hours)

    accounts = config["accounts"]
    interval_hours = config.get("interval_hours", INTERVAL_HOURS)

    # Override interval for login-only testing
    if getattr(args, "login_only", False):
        interval_hours = 1.0 / 60  # 1 minute for testing
        log.info("Login-only mode: interval set to 1 minute.")

    log.info("=== Scheduled Run Started ===")
    log.info("Accounts: %d, Interval: %.2fh, Login-only: %s", len(accounts), interval_hours, getattr(args, "login_only", False))

    # Load state
    state = load_state()

    # Wait if needed (skip in login-only mode)
    if not getattr(args, "login_only", False):
        wait_until_ready(state)
    else:
        log.info("Login-only mode: skipping wait.")

    # Setup proxy
    proxy_list = parse_proxy_pool(getattr(args, "proxy_server", None))
    proxy_pool = ProxyPool(proxy_list) if proxy_list else None

    login_only = getattr(args, "login_only", False)

    if login_only:
        # Login-only mode: run ALL accounts with 1-minute delay
        log.info("=== Login-only mode: testing all %d accounts ===", len(accounts))
        results = []
        for i, account_data in enumerate(accounts):
            log.info("\n--- Account %d/%d: %s ---", i + 1, len(accounts), account_data["account"])
            try:
                completed = await run_account_session(
                    args,
                    account_data["account"],
                    account_data["password"],
                    proxy_pool=proxy_pool,
                )
                results.append((account_data["account"], completed))
                if completed:
                    log.info("✅ Login SUCCESS: %s", account_data["account"])
                else:
                    log.warning("❌ Login FAILED: %s", account_data["account"])
            except Exception as e:
                log.error("💥 Login ERROR: %s — %s", account_data["account"], e)
                results.append((account_data["account"], False))

            # Wait 1 minute between accounts (skip after last)
            if i < len(accounts) - 1:
                log.info("Waiting 60 seconds before next account...")
                await asyncio.sleep(60)

        # Summary
        log.info("\n=== LOGIN TEST SUMMARY ===")
        for account, ok in results:
            status = "✅ OK" if ok else "❌ FAIL"
            log.info("  %s: %s", status, account)
        success_count = sum(1 for _, ok in results if ok)
        log.info("Result: %d/%d accounts successful.", success_count, len(results))

        # Update state
        now = datetime.now(timezone.utc)
        state["last_run_time"] = now.isoformat()
        state["account_index"] = 0
        state["total_runs"] = state.get("total_runs", 0) + 1
        state["history"] = state.get("history", [])
        for account, ok in results:
            state["history"].append({
                "account": account,
                "time": now.isoformat(),
                "completed": ok,
            })
        state["history"] = state["history"][-50:]
        save_state(state)
    else:
        # Normal mode: run ONE account in rotation
        account_index, account_data = get_next_account(accounts, state)
        log.info("Running account: %s", account_data["account"])

        completed = await run_account_session(
            args,
            account_data["account"],
            account_data["password"],
            proxy_pool=proxy_pool,
        )

        # Update state
        now = datetime.now(timezone.utc)
        state["last_run_time"] = now.isoformat()
        state["account_index"] = (account_index + 1) % len(accounts)
        state["total_runs"] = state.get("total_runs", 0) + 1
        state["history"] = state.get("history", [])

        # Keep last 50 history entries
        state["history"].append({
            "account": account_data["account"],
            "time": now.isoformat(),
            "completed": completed,
        })
        state["history"] = state["history"][-50:]

        save_state(state)

        if completed:
            log.info("=== Account completed successfully: %s ===", account_data["account"])
        else:
            log.warning("=== Account failed: %s ===", account_data["account"])
            log.info("Moving to next account for next run.")

        log.info(
            "Next run will pick account index %d (account #%d)",
            state["account_index"],
            state["account_index"] + 1,
        )


def main() -> None:
    uc.loop().run_until_complete(async_main())


if __name__ == "__main__":
    main()
