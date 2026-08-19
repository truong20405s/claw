"""Quick single-account login test."""
from __future__ import annotations

import asyncio
import logging
import sys

import nodriver as uc

from account_rotation import run_account_session


async def test_single_account() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])

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
    completed = await run_account_session(args, "mi12@tempmail.id.vn", "nvt2005S!")
    print(f"\nResult: {'SUCCESS' if completed else 'FAILED'}")
    sys.exit(0 if completed else 1)


if __name__ == "__main__":
    uc.loop().run_until_complete(test_single_account())
