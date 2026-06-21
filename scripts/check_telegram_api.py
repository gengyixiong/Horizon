"""Send one safe Telegram message from the GitHub Actions smoke-test mode.

The bot token and destination chat ID are read only from repository Secrets.
Neither value is printed. This check is intentionally independent of DeepSeek
and the news pipeline, so Telegram delivery can be diagnosed without spending
AI tokens or publishing another daily report.
"""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token:
        print("TELEGRAM_BOT_TOKEN is missing from GitHub Actions Secrets.", file=sys.stderr)
        return 1
    if not chat_id:
        print("TELEGRAM_CHAT_ID is missing from GitHub Actions Secrets.", file=sys.stderr)
        return 1

    # Telegram's Bot API requires the token in the request path. Never print
    # this URL or include it in an exception message.
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🤖 Horizon Telegram 推送已连接\n\n人形机器人日报将在每日更新后自动发送。",
        "link_preview_options": {"is_disabled": True},
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "打开日报站点",
                        "url": "https://gengyixiong.github.io/Horizon/",
                    }
                ]
            ]
        },
    }
    request = Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Horizon/1.0"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            description = error_payload.get("description", "unknown Telegram API error")
        except Exception:
            description = "unknown Telegram API error"
        print(
            f"Telegram Bot API check failed (HTTP {exc.code}): {description}",
            file=sys.stderr,
        )
        return 1
    except (URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", "network error")
        print(f"Telegram Bot API network check failed: {reason}", file=sys.stderr)
        return 1

    if result.get("ok") is not True:
        print(
            f"Telegram Bot API rejected the test: {result.get('description', 'unknown error')}",
            file=sys.stderr,
        )
        return 1

    print("Telegram test message sent successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
