#!/usr/bin/env python3
"""
Telegram Delivery Module — Build, Validate, Log
================================================
The sandbox blocks direct HTTP. The agent calls web_get_contents with the URL
this script builds. This script then validates the response and logs the result.

Credentials come from the environment, never from this file:
  TELEGRAM_BOT_TOKEN   bot token from @BotFather
  TELEGRAM_CHAT_ID     target chat id (e.g. -100123...)

Delivery log: $AI_NEWS_HOME/telegram_delivery_log.json  (same format as the repo copy)
  {"sent": [{"date": "2026-11-02", "message_id": 89, "status": "ok",
             "delivered_at": "2026-11-02T00:41:24Z"}],
   "last_error": {"date": "...", "error": "...", "at": "..."}}

Messages are sent as plain text (no parse_mode), so markup inside scraped
headlines can never turn into links or formatting in the group.

Commands:
  --build "text"              Build URL from inline text, save to file (refuses if already sent today)
  --build --file /path        Build URL from file content
  --build-fallback            Build a short fallback URL from last message
  --validate 'json_response'  Validate web_get_contents response, log result
  --check                     Print today's delivery status
  --status-code               Exit 0 if delivered today, 1 if not

The built URL contains the bot token. It is written to a file and never printed:
do not echo it, log it, or paste it into chat or commit messages.
"""

import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

MAX_URL_LEN = 3800  # Telegram GET URL practical limit (safe margin)
BRIEFING_LINK = "https://dilip457.github.io/ai-news-daily/"
IST = timezone(timedelta(hours=5, minutes=30))
TOKEN_RE = re.compile(r"^\d{5,12}:[A-Za-z0-9_-]{30,}$")
CHAT_ID_RE = re.compile(r"^-?\d{5,20}$")


def _home():
    return os.environ.get("AI_NEWS_HOME", "/scratch/work/notes")


def _work():
    return os.environ.get("AI_NEWS_WORK", "/scratch/work")


def log_path():
    return os.path.join(_home(), "telegram_delivery_log.json")


def url_output_path():
    return os.path.join(_work(), "telegram_url.txt")


def fallback_url_path():
    return os.path.join(_work(), "telegram_retry_url.txt")


def message_save_path():
    return os.path.join(_work(), "telegram_last_message.txt")


class ConfigError(Exception):
    pass


def credentials():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not TOKEN_RE.match(token):
        raise ConfigError("TELEGRAM_BOT_TOKEN is missing or malformed (set it as a secret env var)")
    if not CHAT_ID_RE.match(chat_id):
        raise ConfigError("TELEGRAM_CHAT_ID is missing or malformed (set it as an env var)")
    return token, chat_id


def today_str():
    """The pipeline is dated in IST regardless of the sandbox clock's zone."""
    return datetime.now(IST).strftime("%Y-%m-%d")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_log():
    """Load the delivery log in the repo format, migrating the old flat format."""
    try:
        with open(log_path(), encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"sent": []}
    if not isinstance(log, dict):
        return {"sent": []}
    if not isinstance(log.get("sent"), list):
        # Legacy single-day format: {"date", "status": "delivered", "message_id"}
        legacy = log
        log = {"sent": []}
        if legacy.get("status") == "delivered" and legacy.get("message_id"):
            log["sent"].append({"date": legacy.get("date"), "message_id": legacy["message_id"], "status": "ok"})
    return log


def save_log(log):
    os.makedirs(os.path.dirname(log_path()), exist_ok=True)
    tmp = log_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
        f.write("\n")
    os.replace(tmp, log_path())


def delivery_for(date_str, log=None):
    log = log if log is not None else load_log()
    for entry in log.get("sent", []):
        if isinstance(entry, dict) and entry.get("date") == date_str and entry.get("status") == "ok":
            return entry
    return None


def is_delivered(date_str=None):
    return delivery_for(date_str or today_str()) is not None


def truncate_message(text, max_url_len=MAX_URL_LEN):
    """Truncate message to fit Telegram GET URL limits. Preserves briefing link."""
    base_len = len("https://api.telegram.org/bot<token>/sendMessage?chat_id=&text=") + 60
    max_text_raw = int((max_url_len - base_len - 100) / 1.3)

    if len(text) <= max_text_raw:
        return text

    link_line = f"Read the full briefing:\n{BRIEFING_LINK}"
    result = []
    current_len = 0
    for line in text.split("\n"):
        if BRIEFING_LINK in line:
            continue
        if current_len + len(line) + 1 > max_text_raw - len(link_line) - 20:
            break
        result.append(line)
        current_len += len(line) + 1
    result.append("...")
    result.append(link_line)
    return "\n".join(result)


def build_telegram_url(text):
    token, chat_id = credentials()
    params = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    })
    return f"https://api.telegram.org/bot{token}/sendMessage?{params}"


def _write_private(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)


def build_url(text, output_path=None):
    """Build URL, save it (0600) to a file, save message for retry. Never prints the URL."""
    output_path = output_path or url_output_path()
    text = truncate_message(text)
    url = build_telegram_url(text)
    _write_private(output_path, url)
    _write_private(message_save_path(), text)
    print(f"URL built: {len(url)} chars -> {output_path} (contains the bot token: do not print it)")
    print(f"Message length: {len(text)} chars -> {message_save_path()}")
    return url


def build_fallback():
    """Build a short fallback message from the last saved message."""
    if not os.path.exists(message_save_path()):
        print("ERROR: No previous message found for fallback")
        return None
    with open(message_save_path(), encoding="utf-8") as f:
        lines = f.read().strip().split("\n")

    essential = lines[:1]
    essential += [l for l in lines if "top story" in l.lower()][:1]
    essential += [l for l in lines if "Concept" in l][:1]
    essential += ["", f"Read the full briefing:\n{BRIEFING_LINK}"]
    url = build_telegram_url("\n".join(essential))
    _write_private(fallback_url_path(), url)
    print(f"Fallback URL built: {len(url)} chars -> {fallback_url_path()}")
    return url


def _extract_json(text):
    """web_get_contents may wrap the JSON in other text; find the {"ok": ...} object."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find('{"ok"')
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj
    except json.JSONDecodeError:
        return None


def validate_response(response_text):
    """Returns (success, message_id, error)."""
    try:
        _, chat_id = credentials()
        data = response_text if isinstance(response_text, dict) else _extract_json(str(response_text).strip())
        if not isinstance(data, dict):
            return False, None, "No Telegram JSON found in response"
        if not data.get("ok"):
            return False, None, f"Telegram API error: code={data.get('error_code', '?')}, desc={data.get('description', 'unknown')}"
        result = data.get("result") or {}
        message_id = result.get("message_id")
        if isinstance(message_id, int) and str((result.get("chat") or {}).get("id")) == chat_id:
            return True, message_id, None
        return False, None, "Unexpected response shape (message_id/chat id mismatch)"
    except ConfigError as e:
        return False, None, str(e)
    except Exception as e:  # never let a parsing bug crash the pipeline silently
        return False, None, f"Validation error: {type(e).__name__}"


def log_delivery_result(success, message_id=None, error=None, date_str=None):
    date_str = date_str or today_str()
    log = load_log()
    existing = delivery_for(date_str, log)
    if existing:
        print(f"ALREADY DELIVERED for {date_str}: message_id={existing.get('message_id')} (log unchanged)")
        return
    if success:
        log["sent"].append({"date": date_str, "message_id": message_id, "status": "ok", "delivered_at": utc_now()})
        log.pop("last_error", None)
        print(f"DELIVERY CONFIRMED: message_id={message_id}")
    else:
        log["last_error"] = {"date": date_str, "error": str(error)[:300], "at": utc_now()}
        print(f"DELIVERY FAILED: {error}")
    save_log(log)


def check_status(date_str=None):
    date_str = date_str or today_str()
    log = load_log()
    entry = delivery_for(date_str, log)
    print(f"Date: {date_str}")
    print(f"Delivery Status: {'DELIVERED' if entry else 'NOT DELIVERED'}")
    if entry:
        print(f"Message ID: {entry.get('message_id')}")
    last_error = log.get("last_error")
    if last_error and last_error.get("date") == date_str:
        print(f"Last Error: {last_error.get('error')}")
    return entry


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    try:
        if cmd == "--build":
            if is_delivered():
                print(f"ALREADY DELIVERED for {today_str()} — not building a second message.")
                sys.exit(3)
            if len(sys.argv) > 3 and sys.argv[2] == "--file":
                with open(sys.argv[3], encoding="utf-8") as f:
                    text = f.read()
            elif len(sys.argv) > 2:
                text = sys.argv[2]
            else:
                print("ERROR: No message text provided")
                sys.exit(1)
            build_url(text)
        elif cmd == "--build-fallback":
            if is_delivered():
                print(f"ALREADY DELIVERED for {today_str()} — no fallback needed.")
                sys.exit(3)
            if build_fallback() is None:
                sys.exit(1)
        elif cmd == "--validate":
            response_text = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            success, message_id, error = validate_response(response_text)
            log_delivery_result(success, message_id, error)
            sys.exit(0 if success else 1)
        elif cmd == "--check":
            check_status()
        elif cmd == "--status-code":
            sys.exit(0 if is_delivered() else 1)
        else:
            print(f"Unknown command: {cmd}")
            sys.exit(1)
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
