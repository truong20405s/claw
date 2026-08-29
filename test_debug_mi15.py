"""
Debug test: chạy mi15@tempmail.id.vn qua toàn bộ workflow,
chụp screenshot + dump HTML ở mỗi bước để xác định element nào fail.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import nodriver as uc

# ── Force Chrome path ──────────────────────────────────────
import os
os.environ["CHROME_BIN"] = "/home/work/chromium-local/chrome"

# ── Setup paths ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from nodriver_utils import (
    CSS,
    TEXT,
    build_browser,
    click_element,
    click_when_present,
    error_summary,
    find_element,
    find_elements,
    wait_until_loaded,
)
from mimo_workflow import (
    ANNOUNCEMENT_CLOSE_BUTTON,
    CONTINUE_CREATING_BUTTON,
    COOKIE_ACCEPT_BUTTON,
    CREATE_CONFIRMATION_CHECKBOX,
    CREATE_NOW_BUTTON,
    ENABLED_SEND_PROMPT_BUTTON,
    OTP_INPUT,
    OTP_SUBMIT_BUTTON,
    PASSWORD_INPUT,
    PROMPT_TEXTAREA,
    SEND_EMAIL_BUTTON,
    SIGN_IN_BUTTON,
    SIGN_IN_NAVBAR_BUTTON,
    TERMS_CHECKBOX,
    ACCOUNT_INPUT,
    fill_login_credentials,
    ensure_terms_accepted,
    submit_sign_in,
    submit_otp,
    ensure_creation_confirmation,
    set_prompt_textarea_value,
)
from tempmail_flow import (
    prepare_tempmail_inbox,
    wait_for_otp_from_tempmail,
)

# ── Config ───────────────────────────────────────────────────
TEST_ACCOUNT  = "mi15@tempmail.id.vn"
TEST_PASSWORD = "nvt2005S!"
TEST_URL      = "https://aistudio.xiaomimimo.com/"
CHROME_BIN     = "/opt/ms-playwright/chromium-1228/chrome-linux64/chrome"
SCREENSHOT_DIR = ROOT / "debug_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ROOT / "debug_test.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("debug")

# ── Helpers ──────────────────────────────────────────────────
step_counter = 0

async def step(name: str, tab: uc.Tab, browser: uc.Browser | None = None) -> None:
    """Log step, take screenshot, dump HTML."""
    global step_counter
    step_counter += 1
    tag = f"step{step_counter:02d}_{name}"
    log.info("═══ STEP %d: %s ═══", step_counter, name)

    # Screenshot
    try:
        ss_path = SCREENSHOT_DIR / f"{tag}.png"
        await tab.save_screenshot(str(ss_path), format="png")
        log.info("  📸 Screenshot: %s", ss_path)
    except Exception as e:
        log.warning("  📸 Screenshot failed: %s", e)

    # Current URL & title
    try:
        url = await tab.evaluate("window.location.href", return_by_value=True)
        title = await tab.evaluate("document.title", return_by_value=True)
        log.info("  🌐 URL: %s", url)
        log.info("  📄 Title: %s", title)
    except Exception as e:
        log.warning("  🌐 Could not get URL/title: %s", e)

    # Dump page HTML (first 5000 chars)
    try:
        html = await tab.evaluate(
            "document.documentElement.outerHTML.substring(0, 8000)",
            return_by_value=True,
        )
        html_path = SCREENSHOT_DIR / f"{tag}.html"
        html_path.write_text(html, encoding="utf-8")
        log.info("  📝 HTML dump: %s", html_path)
    except Exception as e:
        log.warning("  📝 HTML dump failed: %s", e)

    # List all visible buttons
    try:
        buttons = await find_elements(tab, (CSS, "button, a[role='button'], [role='button']"), timeout=0)
        log.info("  🔘 Visible buttons (%d):", len(buttons))
        for i, btn in enumerate(buttons[:20]):
            try:
                text = (btn.text_all or "").strip()[:60]
                attrs = btn.attrs if hasattr(btn, 'attrs') else {}
                track = attrs.get("data-track-id", "")
                cls = attrs.get("class", "")[:50]
                log.info("    [%d] text=%r track=%r class=%r", i, text, track, cls)
            except Exception:
                pass
    except Exception as e:
        log.warning("  🔘 Could not list buttons: %s", e)

    # List all visible inputs
    try:
        inputs = await find_elements(tab, (CSS, "input, textarea"), timeout=0)
        log.info("  📝 Visible inputs (%d):", len(inputs))
        for i, inp in enumerate(inputs[:15]):
            try:
                attrs = inp.attrs if hasattr(inp, 'attrs') else {}
                name = attrs.get("name", "")
                placeholder = attrs.get("placeholder", "")
                aria = attrs.get("aria-label", "")
                itype = attrs.get("type", "")
                log.info("    [%d] name=%r placeholder=%r aria=%r type=%r", i, name, placeholder, aria, itype)
            except Exception:
                pass
    except Exception as e:
        log.warning("  📝 Could not list inputs: %s", e)


async def try_find(locator, tab, name, timeout=5):
    """Try to find an element, log result, return (element, found)."""
    try:
        el = await find_element(tab, locator, timeout)
        log.info("  ✅ Found: %s", name)
        return el, True
    except Exception as e:
        log.warning("  ❌ NOT found: %s — %s", name, error_summary(e))
        return None, False


# ── Main ─────────────────────────────────────────────────────
async def main() -> None:
    log.info("=== DEBUG TEST START: %s ===", TEST_ACCOUNT)
    browser = None
    tab = None
    try:
        # ── Build browser ──
        log.info("Building browser (headless=True)...")
        browser = await asyncio.wait_for(
            build_browser(headless=True),
            timeout=60,
        )
        tab = await browser.get("about:blank")
        log.info("Browser ready.")

        # ── Step 1: Navigate ──
        log.info("Navigating to %s...", TEST_URL)
        await tab.send(uc.cdp.page.navigate(TEST_URL))
        await wait_until_loaded(tab, timeout=30)
        await step("navigate", tab, browser)

        # ── Step 2: Dismiss popups ──
        await click_when_present(tab, ANNOUNCEMENT_CLOSE_BUTTON, "Announcement Close", timeout=3)
        await click_when_present(tab, COOKIE_ACCEPT_BUTTON, "Cookie Accept", timeout=2)
        await step("dismiss_popups", tab, browser)

        # ── Step 3: Click Create Now or Sign In ──
        create_clicked = await click_when_present(tab, CREATE_NOW_BUTTON, "Create Now", timeout=10)
        if not create_clicked:
            await click_when_present(tab, SIGN_IN_NAVBAR_BUTTON, "Navbar Sign in", timeout=5)
        await step("click_create_or_signin", tab, browser)

        # ── Step 4: Wait for Xiaomi login page ──
        log.info("Waiting for Xiaomi login page...")
        try:
            await wait_until_loaded(tab, timeout=30, expected_url_contains="account.xiaomi.com")
            log.info("  ✅ Xiaomi login page loaded")
        except Exception as e:
            log.warning("  ⚠️ Xiaomi login page wait: %s", error_summary(e))
        await step("xiaomi_login_page", tab, browser)

        # ── Step 5: Terms checkbox ──
        terms_ok = await ensure_terms_accepted(tab, timeout=15)
        log.info("  Terms accepted: %s", terms_ok)
        await step("terms_checkbox", tab, browser)

        # ── Step 6: Fill credentials ──
        cred_ok = await fill_login_credentials(tab, TEST_ACCOUNT, TEST_PASSWORD, timeout=15)
        log.info("  Credentials filled: %s", cred_ok)
        await step("fill_credentials", tab, browser)

        # ── Step 7: Submit sign-in ──
        signin_ok = await submit_sign_in(tab, timeout=15)
        log.info("  Sign-in submitted: %s", signin_ok)
        await step("submit_signin", tab, browser)

        # ── Step 8: Wait for verification page ──
        log.info("Waiting for Send Email button (verification page)...")
        send_email_el, send_email_found = await try_find(SEND_EMAIL_BUTTON, tab, "Send Email Button", timeout=30)
        await step("verification_page", tab, browser)

        if not send_email_found:
            log.error("❌ BLOCKED: Send Email button not found. Login may have failed.")
            # Try to see what's on the page
            try:
                page_text = await tab.evaluate("document.body.innerText.substring(0, 3000)", return_by_value=True)
                log.info("  Page text: %s", page_text[:1000])
            except Exception:
                pass
            return

        # ── Step 9: Prepare TempMail inbox ──
        inbox = await prepare_tempmail_inbox(browser, TEST_ACCOUNT, original_tab=tab, timeout=15)
        if inbox is None:
            log.error("❌ BLOCKED: Could not prepare TempMail inbox.")
            return
        log.info("  TempMail inbox ready: %s", inbox.email)
        await step("tempmail_ready", tab, browser)

        # ── Step 10: Click Send Email ──
        send_clicked = await click_when_present(tab, SEND_EMAIL_BUTTON, "Send Email", timeout=10)
        log.info("  Send Email clicked: %s", send_clicked)
        await step("send_email_clicked", tab, browser)

        # ── Step 11: Wait for OTP ──
        log.info("Waiting for OTP (up to 120s)...")
        otp = await wait_for_otp_from_tempmail(inbox, otp_timeout=120)
        if not otp:
            log.error("❌ BLOCKED: No OTP received.")
            await step("otp_timeout", tab, browser)
            return
        log.info("  OTP received: %s", otp)
        await step("otp_received", tab, browser)

        # ── Step 12: Submit OTP ──
        otp_ok = await submit_otp(tab, otp, timeout=15)
        log.info("  OTP submitted: %s", otp_ok)
        await step("otp_submitted", tab, browser)

        # ── Step 13: Post-OTP — check new vs existing workspace ──
        log.info("Checking post-OTP state...")
        create_now_clicked = await click_when_present(
            tab, CREATE_NOW_BUTTON, "Create Now after OTP", timeout=10,
        )
        log.info("  Create Now clicked: %s", create_now_clicked)
        await step("post_otp_create_now", tab, browser)

        if create_now_clicked:
            confirmed = await ensure_creation_confirmation(tab, timeout=10)
            log.info("  Creation confirmed: %s", confirmed)
            await step("creation_confirmed", tab, browser)

        # ── Step 14: Wait for workspace / prompt textarea ──
        log.info("Waiting for prompt textarea (up to 150s)...")
        textarea_ok = False
        deadline = time.monotonic() + 150
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            remaining = max(1, deadline - time.monotonic())
            log.info("  Attempt %d (%.0fs left)...", attempt, remaining)
            try:
                textarea = await find_element(tab, PROMPT_TEXTAREA, timeout=min(15, remaining))
                log.info("  ✅ Prompt textarea FOUND!")
                textarea_ok = True
                break
            except Exception as e:
                log.warning("  ❌ Prompt textarea NOT found: %s", error_summary(e))
                # Dump what's on the page
                try:
                    url = await tab.evaluate("window.location.href", return_by_value=True)
                    log.info("  Current URL: %s", url)
                    all_inputs = await find_elements(tab, (CSS, "input, textarea"), timeout=0)
                    log.info("  All inputs on page: %d", len(all_inputs))
                    for i, inp in enumerate(all_inputs[:10]):
                        try:
                            attrs = inp.attrs if hasattr(inp, 'attrs') else {}
                            log.info("    [%d] tag=%r name=%r placeholder=%r", 
                                     i, attrs.get("tag",""), attrs.get("name",""), attrs.get("placeholder",""))
                        except Exception:
                            pass
                except Exception:
                    pass
                await step(f"textarea_search_attempt{attempt}", tab, browser)
                await asyncio.sleep(5)

        await step("textarea_final", tab, browser)

        if not textarea_ok:
            log.error("❌ BLOCKED: Prompt textarea never appeared after 150s.")
            # Final page analysis
            try:
                page_text = await tab.evaluate("document.body.innerText.substring(0, 5000)", return_by_value=True)
                log.info("  Final page text:\n%s", page_text[:2000])
            except Exception:
                pass
            return

        # ── Step 15: Type prompt ──
        await click_element(textarea)
        await tab.sleep(0.5)
        await textarea.clear_input()
        test_prompt = "Hello, this is a test prompt from debug script."
        actual = await set_prompt_textarea_value(textarea, test_prompt)
        log.info("  Prompt typed: %r (expected: %r)", actual, test_prompt)
        await step("prompt_typed", tab, browser)

        # ── Step 16: Find and click send ──
        send_btn, send_found = await try_find(ENABLED_SEND_PROMPT_BUTTON, tab, "Send Prompt Button", timeout=10)
        await step("send_button", tab, browser)

        if send_found:
            log.info("✅ ALL STEPS PASSED! Ready to send prompt.")
        else:
            log.warning("⚠️ Send button not found, but textarea works.")

    except Exception as e:
        log.error("💥 CRASH: %s", error_summary(e))
        if tab is not None:
            try:
                await step("crash", tab, browser)
            except Exception:
                pass
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass
        log.info("=== DEBUG TEST END ===")
        log.info("Screenshots saved in: %s", SCREENSHOT_DIR)


if __name__ == "__main__":
    uc.loop().run_until_complete(main())
