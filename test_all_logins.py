"""Test login for all enabled accounts."""
from __future__ import annotations

import asyncio
import json
import logging
import sys

import nodriver as uc

from account_rotation import run_account_session


async def test_all_accounts() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])

    with open("accounts.json") as f:
        data = json.load(f)

    accounts = [a for a in data["accounts"] if a.get("enabled", True)]
    print(f"\n{'='*50}")
    print(f"Testing login for {len(accounts)} accounts")
    print(f"{'='*50}\n")

    results = {}
    for i, acc in enumerate(accounts, 1):
        email = acc["account"]
        password = acc["password"]
        print(f"\n[{i}/{len(accounts)}] Testing: {email}")

        class Args:
            headless = True
            login_only = True
            url = "https://aistudio.xiaomimimo.com/"
            timeout = 60
            prompt_source = ""
            screenshot = ""
            otp_timeout = 120
            proxy_server = None
            log_level = "INFO"
            config = "accounts.json"
            interval_hours = None
            account = ""
            password = ""

        args = Args()
        try:
            completed = await run_account_session(args, email, password)
            status = "✅ SUCCESS" if completed else "❌ FAILED"
        except Exception as e:
            status = f"❌ ERROR: {e}"
            completed = False

        results[email] = completed
        print(f"  → {status}")

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    success = sum(1 for v in results.values() if v)
    failed = len(results) - success
    for email, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {email}")
    print(f"\nTotal: {success} success, {failed} failed out of {len(results)}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    uc.loop().run_until_complete(test_all_accounts())
