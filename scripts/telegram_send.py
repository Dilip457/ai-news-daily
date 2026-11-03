#!/usr/bin/env python3
"""
Telegram delivery — runner side
===============================
Runs inside GitHub Actions, which has direct internet access. That is the whole
point of this script: the bot token is read from a repository secret on the
runner and never placed in a URL built in the agent sandbox, so it cannot end up
in a transcript, a 0600 temp file or a third-party fetch service.

CI-only: like deploy_gate.py and repo_audit.py, this file is NOT listed in
scripts/checksums.json (the agent never executes it) and bootstrap.py does not
download it.

Inputs
  telegram/outbox.json     {"date": "YYYY-MM-DD", "text": "...", "kind": "briefing"|"alert"}
                           written by the agent. "kind" defaults to "briefing".
                           At most one briefing AND at most one alert per date: an
                           alert must still get through after the briefing was sent
                           (e.g. when the deploy fails), but can never repeat.
  TELEGRAM_BOT_TOKEN       repository secret
  TELEGRAM_CHAT_ID         repository secret
Outputs
  telegram_delivery_log.json   briefing -> appended to "sent"; alert -> appended to
                               "alerts"; failure -> last_error
  telegram/outbox.json         consumed (removed by the workflow, not here)

Exit codes
  0  sent, already sent for that date, or nothing to send (all green)
  1  delivery failed (log records last_error)
  2  config error (a secret is missing or malformed)
  3  dry run completed

Usage
  python3 scripts/telegram_send.py             # send
  python3 scripts/telegram_send.py --dry-run   # build + validate payload, no network
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

OUTBOX = os.path.join("telegram", "outbox.json")
LOG = "telegram_delivery_log.json"
BRIEFING_LINK = "https://dilip457.github.io/ai-news-daily/"
API = "https://api.telegram.org"
IST = timezone(timedelta(hours=5, minutes=30))

MAX_TEXT = 4000  # Telegram hard limit is 4096; keep a margin
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KINDS = ("briefing", "alert")
TOKEN_RE = re.compile(r"^\d{5,12}:[A-Za-z0-9_-]{30,}$")
CHAT_ID_RE = re.compile(r"^-?\d{5,20}$")

RETRIES = 3
BACKOFF_BASE = 2  # seconds: 2, 4, 8


class ConfigError(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def credentials():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not TOKEN_RE.match(token):
        raise ConfigError("TELEGRAM_BOT_TOKEN secret is missing or malformed")
    if not CHAT_ID_RE.match(chat_id):
        raise ConfigError("TELEGRAM_CHAT_ID secret is missing or malformed")
    return token, chat_id


def load_outbox():
    try:
        with open(OUTBOX, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"telegram/outbox.json is unreadable: {type(e).__name__}")
    if not isinstance(data, dict):
        raise ConfigError("telegram/outbox.json must be an object")
    date = str(data.get("date", "")).strip()
    text = data.get("text")
    if not DATE_RE.match(date):
        raise ConfigError("telegram/outbox.json: date must be YYYY-MM-DD")
    if not isinstance(text, str) or not text.strip():
        raise ConfigError("telegram/outbox.json: text is empty")
    kind = data.get("kind", "briefing")
    if kind not in KINDS:
        raise ConfigError(f"telegram/outbox.json: kind must be one of {KINDS}")
    return date, text, kind


def load_log():
    try:
        with open(LOG, encoding="utf-8") as f:
            log = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"sent": []}
    if not isinstance(log, dict):
        return {"sent": []}
    if not isinstance(log.get("sent"), list):
        return {"sent": []}
    return log


def save_log(log):
    tmp = LOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
        f.write("\n")
    os.replace(tmp, LOG)


def delivered(date, log, kind="briefing"):
    entries = log.get("alerts", []) if kind == "alert" else log.get("sent", [])
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("date") == date and entry.get("status") == "ok":
            return entry
    return None


def truncate(text, limit=MAX_TEXT):
    """Fit Telegram's 4096-char cap while keeping the briefing link reachable."""
    if len(text) <= limit:
        return text
    link_line = f"Read the full briefing:\n{BRIEFING_LINK}"
    budget = limit - len(link_line) - 24
    kept, used = [], 0
    for line in text.split("\n"):
        if BRIEFING_LINK in line:
            continue
        if used + len(line) + 1 > budget:
            break
        kept.append(line)
        used += len(line) + 1
    kept += ["...", link_line]
    return "\n".join(kept)


def post(token, payload, timeout=30):
    """One POST to sendMessage. Returns (ok, data, http_status)."""
    url = f"{API}/bot{token}/sendMessage"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read().decode("utf-8", "replace")), r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return False, json.loads(raw), e.code
        except json.JSONDecodeError:
            return False, {"description": "unparseable error body"}, e.code
    except (urllib.error.URLError, OSError) as e:
        # Never echo the URL: it carries the token. The type alone is enough.
        return False, {"description": f"network error: {type(e).__name__}"}, 0


def send_with_retries(token, payload):
    """Exponential backoff on 429/5xx. Returns (message_id, error)."""
    last = "unknown error"
    for attempt in range(RETRIES):
        ok, data, status = post(token, payload)
        if ok and data.get("ok"):
            result = data.get("result") or {}
            mid = result.get("message_id")
            if isinstance(mid, int):
                return mid, None
            return None, "response missing message_id"
        desc = str(data.get("description", "unknown"))[:200]
        code = data.get("error_code", status)
        last = f"code={code}, desc={desc}"
        if code == 429 or (isinstance(code, int) and code >= 500):
            retry_after = (data.get("parameters") or {}).get("retry_after")
            wait = int(retry_after) if isinstance(retry_after, int) else BACKOFF_BASE ** (attempt + 1)
            wait = min(wait, 60)
            print(f"attempt {attempt + 1}: {last} — retrying in {wait}s")
            time.sleep(wait)
            continue
        return None, last  # 4xx other than 429: retrying cannot help
    return None, last


def main():
    dry = "--dry-run" in sys.argv[1:]

    try:
        outbox = load_outbox()
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}")
        return 2
    if outbox is None:
        print("Nothing to send: telegram/outbox.json is absent (already consumed).")
        return 0
    date, text, kind = outbox

    log = load_log()
    existing = delivered(date, log, kind)
    if existing:
        print(f"ALREADY DELIVERED ({kind}) for {date}: message_id={existing.get('message_id')} — not sending again.")
        return 0

    try:
        token, chat_id = credentials()
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}")
        return 2

    body = truncate(text)
    payload = {
        "chat_id": chat_id,
        "text": body,
        "disable_web_page_preview": True,
    }
    print(f"Date: {date}  Kind: {kind}")
    print(f"Message: {len(body)} chars (limit {MAX_TEXT}), plain text, preview disabled")

    if dry:
        print("DRY RUN: payload built and valid; nothing sent.")
        return 3

    message_id, error = send_with_retries(token, payload)
    if error:
        log["last_error"] = {"date": date, "error": str(error)[:300], "at": utc_now()}
        save_log(log)
        print(f"DELIVERY FAILED: {error}")
        return 1

    entry = {"date": date, "message_id": message_id, "status": "ok", "delivered_at": utc_now()}
    if kind == "alert":
        if not isinstance(log.get("alerts"), list):
            log["alerts"] = []
        log["alerts"].append(entry)
    else:
        log["sent"].append(entry)
    log.pop("last_error", None)
    save_log(log)
    print(f"DELIVERY CONFIRMED: message_id={message_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
