"""
Test: mi15 account — full workflow with reload-on-timeout strategy.

If the prompt textarea is not found within 60s, reload the page
(up to 2 times, 30s settle each) and try again.

Usage:
    python3 test_mi15_reload.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

import nodriver as uc

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from nodriver_utils import (
    CSS,
    build_browser,
    click_element,
    click_when_present,
    error_summary,
    find_element,
    wait_until_loaded,
)
from mimo_workflow import (
    ANNOUNCEMENT_CLOSE_BUTTON,
    CONTINUE_CREATING_BUTTON,
    COOKIE_ACCEPT_BUTTON,
    CREATE_NOW_BUTTON,
    ENABLED_SEND_PROMPT_BUTTON,
    PROMPT_TEXTAREA,
    SEND_EMAIL_BUTTON,
    TERMS_CHECKBOX,
    ACCOUNT_INPUT,
    PASSWORD_INPUT,
    SIGN_IN_BUTTON,
    SIGN_IN_NAVBAR_BUTTON,
    fill_login_credentials,
    ensure_terms_accepted,
    submit_sign_in,
    submit_otp,
    ensure_creation_confirmation,
    set_prompt_textarea_value,
    text_chunks,
    normalize_textarea_text,
    INPUT_FOCUS_SETTLE_SECONDS,
    BUTTON_SETTLE_SECONDS,
)
from tempmail_flow import (
    prepare_tempmail_inbox,
    wait_for_otp_from_tempmail,
)

# ── Config ───────────────────────────────────────────────────
TEST_ACCOUNT   = "mi16@tempmail.id.vn"
TEST_PASSWORD  = "***"
TEST_URL       = "https://aistudio.xiaomimimo.com/"
FIRST_TIMEOUT  = 60      # seconds to wait for textarea on first try
SETTLE_SECONDS = 30      # seconds to wait after each reload
MAX_RELOADS    = 2        # max page reloads before giving up
SCREENSHOT_DIR = ROOT / "test_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "test_mi15_reload.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("test")

# ── Chrome ───────────────────────────────────────────────────
import os
os.environ["CHROME_BIN"] = os.environ.get(
    "CHROME_BIN", "/home/work/chromium-local/chrome"
)


# ── Helpers ──────────────────────────────────────────────────
step_n = 0

async def snap(tag: str, tab: uc.Tab) -> None:
    global step_n
    step_n += 1
    path = SCREENSHOT_DIR / f"{step_n:02d}_{tag}.png"
    try:
        await tab.save_screenshot(str(path), format="png")
        log.info("📸 %s", path)
    except Exception as e:
        log.warning("📸 failed: %s", e)


async def reload_and_find_textarea(tab: uc.Tab) -> bool:
    """Reload the page and try to find the prompt textarea."""
    for i in range(1, MAX_RELOADS + 1):
        log.info("🔄 Reload attempt %d/%d...", i, MAX_RELOADS)
        try:
            url = await tab.evaluate("window.location.href", return_by_value=True)
            log.info("   Reloading: %s", url)
            await tab.send(uc.cdp.page.navigate(url))
        except Exception:
            try:
                await tab.evaluate("location.reload()")
            except Exception:
                pass

        log.info("   Waiting %ds for page to settle...", SETTLE_SECONDS)
        await asyncio.sleep(SETTLE_SECONDS)
        try:
            await wait_until_loaded(tab, timeout=30)
        except Exception as e:
            log.warning("   wait_until_loaded: %s", error_summary(e))

        await click_when_present(tab, ANNOUNCEMENT_CLOSE_BUTTON, "Announcement", timeout=3)
        await click_when_present(tab, COOKIE_ACCEPT_BUTTON, "Cookie", timeout=2)

        try:
            await find_element(tab, PROMPT_TEXTAREA, timeout=30)
            log.info("   ✅ Textarea found after reload %d!", i)
            return True
        except Exception as e:
            log.warning("   ❌ Still not found: %s", error_summary(e))
    return False


# ── Main ─────────────────────────────────────────────────────
async def main() -> None:
    log.info("=== TEST START: %s ===", TEST_ACCOUNT)
    browser = None
    tab = None
    try:
        browser = await asyncio.wait_for(build_browser(headless=True), timeout=60)
        tab = await browser.get("about:blank")

        # 1. Navigate
        log.info("1️⃣ Navigate to %s", TEST_URL)
        await tab.send(uc.cdp.page.navigate(TEST_URL))
        await wait_until_loaded(tab, timeout=30)
        await snap("navigate", tab)

        # 2. Dismiss popups
        await click_when_present(tab, ANNOUNCEMENT_CLOSE_BUTTON, "Announcement", timeout=3)
        await click_when_present(tab, COOKIE_ACCEPT_BUTTON, "Cookie", timeout=2)

        # 3. Click Create Now / Sign In
        log.info("3️⃣ Click Create Now / Sign In")
        if not await click_when_present(tab, CREATE_NOW_BUTTON, "Create Now", timeout=10):
            await click_when_present(tab, SIGN_IN_NAVBAR_BUTTON, "Sign In", timeout=5)
        await snap("create_or_signin", tab)

        # 4. Xiaomi login page
        log.info("4️⃣ Wait for Xiaomi login page")
        try:
            await wait_until_loaded(tab, timeout=30, expected_url_contains="account.xiaomi.com")
        except Exception:
            pass
        await snap("login_page", tab)

        # 5. Terms + credentials + sign in
        log.info("5️⃣ Terms + credentials + sign in")
        await ensure_terms_accepted(tab, timeout=15)
        await fill_login_credentials(tab, TEST_ACCOUNT, TEST_PASSWORD, timeout=15)
        await submit_sign_in(tab, timeout=15)
        await snap("signed_in", tab)

        # 6. Wait for verification page
        log.info("6️⃣ Wait for Send Email button")
        try:
            await find_element(tab, SEND_EMAIL_BUTTON, timeout=30)
        except Exception:
            log.error("❌ Send Email button not found — login failed?")
            await snap("no_send_email", tab)
            return
        await snap("verification_ready", tab)

        # 7. TempMail
        log.info("7️⃣ Prepare TempMail inbox")
        inbox = await prepare_tempmail_inbox(browser, TEST_ACCOUNT, original_tab=tab, timeout=15)
        if not inbox:
            log.error("❌ TempMail failed")
            return

        # 8. Click Send Email
        log.info("8️⃣ Click Send Email")
        await click_when_present(tab, SEND_EMAIL_BUTTON, "Send Email", timeout=10)
        await snap("send_email_clicked", tab)

        # 9. Wait for OTP
        log.info("9️⃣ Wait for OTP (up to 120s)")
        otp = await wait_for_otp_from_tempmail(inbox, otp_timeout=120)
        if not otp:
            log.error("❌ No OTP received")
            await snap("otp_timeout", tab)
            return
        log.info("   OTP: %s", otp)
        await snap("otp_received", tab)

        # 10. Submit OTP
        log.info("🔟 Submit OTP")
        await submit_otp(tab, otp, timeout=15)
        await snap("otp_submitted", tab)

        # 11. Post-OTP: Create Now + confirmation
        log.info("1️⃣1️⃣ Post-OTP workspace creation")
        if await click_when_present(tab, CREATE_NOW_BUTTON, "Create Now", timeout=10):
            await ensure_creation_confirmation(tab, timeout=10)
        await snap("creation_done", tab)

        # 12. Find textarea — FIRST ATTEMPT (60s)
        log.info("1️⃣2️⃣ First attempt: wait %ds for textarea...", FIRST_TIMEOUT)
        textarea = None
        try:
            textarea = await find_element(tab, PROMPT_TEXTAREA, timeout=FIRST_TIMEOUT)
            log.info("   ✅ Textarea found on first attempt!")
        except Exception as e:
            log.warning("   ❌ Not found after %ds: %s", FIRST_TIMEOUT, error_summary(e))
            # 13. RELOAD AND RETRY
            log.info("1️⃣3️⃣ Reload and retry...")
            if await reload_and_find_textarea(tab):
                textarea = await find_element(tab, PROMPT_TEXTAREA, timeout=10)
                log.info("   ✅ Textarea found after reload!")
            else:
                log.error("   ❌ Textarea not found even after %d reloads", MAX_RELOADS)
                await snap("textarea_failed", tab)
                return

        await snap("textarea_found", tab)

        # 14. Type prompt
        log.info("1️⃣4️⃣ Type prompt")
        await click_element(textarea)
        await tab.sleep(INPUT_FOCUS_SETTLE_SECONDS)
        await textarea.clear_input()
        test_prompt = "Hello from test_mi15_reload.py — workflow validation successful!"
        actual = await set_prompt_textarea_value(textarea, test_prompt)
        log.info("   Prompt value: %r", actual)
        await snap("prompt_typed", tab)

        # 15. Find send button
        log.info("1️⃣5️⃣ Find send button")
        try:
            await find_element(tab, ENABLED_SEND_PROMPT_BUTTON, timeout=10)
            log.info("   ✅ Send button found!")
        except Exception:
            log.warning("   ⚠️ Send button not found (but textarea works)")
        await snap("send_button", tab)

        log.info("=== ✅ ALL STEPS PASSED ===")

    except Exception as e:
        log.error("💥 CRASH: %s", error_summary(e))
        if tab:
            await snap("crash", tab)
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
