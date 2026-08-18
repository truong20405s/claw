# Auto Login MiMo

This project runs as a background worker. It does not expose an HTTP port.

## Railway deployment

Railpack reads `railpack.json`, installs Chromium, and starts the nodriver worker
with `python app.py --headless`. Linux servers without a display automatically
enable headless mode as well.

Deploy `accounts.json` together with the source. Its structure is:

```json
{"interval_hours":4,"accounts":[{"account":"first@example.com","password":"secret"}]}
```

The prompt is loaded from this Google Drive file by default:

```text
https://drive.google.com/file/d/1SXbCW-6bFvVvsq70xtb_rk3thTscc2cP/view?usp=drive_link
```

Set the token either in the uploaded `.env` file or as a Railway service
variable (the Railway variable takes precedence):

- `TELEGRAM_BOT_TOKEN`: Telegram bot token inserted into the prompt at runtime
- `TEMPMAIL_API_TOKEN`: Token for TempMail API
- `PROXY_POOL` (hoặc `PROXY_SERVER`): Danh sách proxy tự động xoay tua (phân cách bằng dấu phẩy), ví dụ:
  `socks5://38.180.9.158:4422,socks5://43.106.60.21:1080,socks5://8.219.97.248:80`

To use another prompt file, pass a local path or URL:

```powershell
python app.py --prompt-source .\custom-prompt.txt --once
```

Do not commit a populated `.env` file. It is ignored by Git.

## Local run

Set `TELEGRAM_BOT_TOKEN`, install `requirements.txt`, and run:

```powershell
python app.py --once
```

The TempMail inbox is prepared before Xiaomi sends a verification email. Existing
messages are recorded and ignored, so only a newly received email can provide the
OTP. A failed account switches immediately to the next account; the configured
rotation interval is applied only after a completed account session. If every
account in a cycle fails, the worker waits five minutes before retrying so a
website outage cannot create a tight retry loop.
