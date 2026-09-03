"""Test login for all enabled accounts with screenshot on failure."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import nodriver as uc

from account_rotation import run_account_session

SCREENSHOT_DIR = "test_screenshots"


async def test_all_accounts() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    with open("accounts.json") as f:
        data = json.load(f)

    accounts = [a for a in data["accounts"] if a.get("enabled", True)]
    print(f"\n{'='*50}")
    print(f"Testing login for {len(accounts)} accounts")
    print(f"{'='*50}\n")

    results = {}
    errors = {}
    for i, acc in enumerate(accounts, 1):
        email = acc["account"]
        password = acc["password"]
        safe_name = email.replace("@", "_at_").replace(".", "_")
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
            if completed:
                status = "✅ SUCCESS"
            else:
                status = "❌ FAILED"
                # Take screenshot on failure
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ss_path = os.path.join(SCREENSHOT_DIR, f"fail_{safe_name}_{ts}.png")
                    # Try to get browser and screenshot
                    browser = await uc.start(headless=True)
                    page = await browser.get("https://aistudio.xiaomimimo.com/")
                    await page.save_screenshot(ss_path)
                    browser.stop()
                    print(f"  📸 Screenshot saved: {ss_path}")
                except Exception as ss_err:
                    print(f"  ⚠️ Could not capture screenshot: {ss_err}")
                errors[email] = "Login returned False (likely OTP timeout or page error)"
        except Exception as e:
            status = f"❌ ERROR: {e}"
            completed = False
            errors[email] = str(e)
            # Take screenshot on exception
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                ss_path = os.path.join(SCREENSHOT_DIR, f"error_{safe_name}_{ts}.png")
                browser = await uc.start(headless=True)
                page = await browser.get("https://aistudio.xiaomimimo.com/")
                await page.save_screenshot(ss_path)
                browser.stop()
                print(f"  📸 Screenshot saved: {ss_path}")
            except Exception as ss_err:
                print(f"  ⚠️ Could not capture screenshot: {ss_err}")

        results[email] = completed
        print(f"  → {status}")

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    success = sum(1 for v in results.values() if v)
    failed = len(results) - success
    for email, ok in results.items():
        icon = '✅' if ok else '❌'
        err_info = f" — {errors[email]}" if email in errors else ""
        print(f"  {icon} {email}{err_info}")
    print(f"\nTotal: {success} success, {failed} failed out of {len(results)}")

    # Write error report
    if errors:
        report_path = os.path.join(SCREENSHOT_DIR, "error_report.txt")
        with open(report_path, "w") as f:
            f.write(f"Login Test Error Report - {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n\n")
            for email, err in errors.items():
                f.write(f"❌ {email}\n   Error: {err}\n\n")
        print(f"\n📝 Error report: {report_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    uc.loop().run_until_complete(test_all_accounts())
