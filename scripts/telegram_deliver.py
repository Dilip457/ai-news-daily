#!/usr/bin/env python3
"""
Telegram Delivery Module — Build, Send, Validate, Retry
=========================================================
Replaces send_telegram.py with full delivery tracking.

The sandbox blocks direct HTTP. The agent calls web_get_contents with the URL
this script builds. This script then validates the response and logs the result.

Delivery log: /workspace/notes/telegram_delivery_log.json
   { "date": "2026-09-05", "status": "delivered|failed|pending",
     "message_id": 28, "attempts": 1, "last_error": null, "timestamp": "..." }

Commands:
  --build "text"              Build URL from inline text, save to file
  --build --file /path        Build URL from file content
  --build-fallback            Build a short fallback URL from last message
  --validate 'json_response'  Validate web_get_contents response, log result
  --check                     Print delivery status from log
  --reset                     Reset log to pending (new day)
  --status-code               Exit 0 if delivered, 1 if not (for pipeline checks)
"""

import sys
import json
import os
import urllib.parse
from datetime import datetime, timezone

BOT_TOKEN = "8645739822:AAFQrtZ1czXuDm9USN8Z8j4tpAS9HM2Q4V0"
CHAT_ID = "-5322260984"
MAX_URL_LEN = 3800  # Telegram GET URL practical limit (safe margin)
BRIEFING_LINK = "https://dilip457.github.io/ai-news-daily/"

# Persistent paths (in /workspace/ which survives sandbox restarts)
LOG_PATH = "/workspace/notes/telegram_delivery_log.json"
URL_OUTPUT_PATH = "/workspace/input/telegram_url.txt"
MESSAGE_SAVE_PATH = "/workspace/notes/telegram_last_message.txt"
FALLBACK_URL_PATH = "/workspace/input/telegram_retry_url.txt"


def now_ist():
    """Current timestamp in IST."""
    return datetime.now(timezone(offset=datetime.now().astimezone().utcoffset())).isoformat()


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def load_log():
    """Load the delivery log, or create a fresh one."""
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "date": today_str(),
        "status": "pending",
        "message_id": None,
        "attempts": 0,
        "last_error": None,
        "timestamp": now_ist(),
    }


def save_log(log):
    """Save the delivery log."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def reset_log():
    """Reset the log for a new day."""
    log = {
        "date": today_str(),
        "status": "pending",
        "message_id": None,
        "attempts": 0,
        "last_error": None,
        "timestamp": now_ist(),
    }
    save_log(log)
    print(f"Log reset: {json.dumps(log)}")


def truncate_message(text, max_url_len=MAX_URL_LEN):
    """Truncate message to fit Telegram GET URL limits. Preserves briefing link."""
    base = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&parse_mode=HTML&text="
    max_text_encoded = max_url_len - len(base) - 100
    max_text_raw = int(max_text_encoded / 1.3)

    if len(text) <= max_text_raw:
        return text

    lines = text.split("\n")
    link_line = f"Read the full briefing:\n{BRIEFING_LINK}"

    result = []
    current_len = 0
    for line in lines:
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
    """Build the Telegram sendMessage API URL."""
    base = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "parse_mode": "HTML",
        "text": text
    })
    return f"{base}?{params}"


def build_url(text, output_path=URL_OUTPUT_PATH):
    """Build URL, save to file, save message for retry."""
    text = truncate_message(text)
    url = build_telegram_url(text)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(url)
    with open(MESSAGE_SAVE_PATH, "w") as f:
        f.write(text)

    print(f"URL built: {len(url)} chars")
    print(f"Message length: {len(text)} chars")
    print(f"URL saved to: {output_path}")
    print(f"Message saved to: {MESSAGE_SAVE_PATH}")
    return url


def build_fallback():
    """Build a short fallback message from the last saved message."""
    if not os.path.exists(MESSAGE_SAVE_PATH):
        print("ERROR: No previous message found for fallback")
        return None

    with open(MESSAGE_SAVE_PATH) as f:
        original = f.read()

    # Extract just the essentials: date line, top story, link
    lines = original.strip().split("\n")
    essential = []

    # Keep the title line (first line)
    if lines:
        essential.append(lines[0])

    # Find "Top story" line
    for line in lines:
        if "Top story" in line or "top story" in line.lower():
            essential.append(line)
            break

    # Find concept line
    for line in lines:
        if "Concept" in line:
            essential.append(line)
            break

    essential.append("")
    essential.append(f"Read the full briefing:\n{BRIEFING_LINK}")

    fallback_text = "\n".join(essential)
    url = build_telegram_url(fallback_text)

    with open(FALLBACK_URL_PATH, "w") as f:
        f.write(url)

    print(f"Fallback URL built: {len(url)} chars")
    print(f"Fallback message: {len(fallback_text)} chars")
    print(f"Saved to: {FALLBACK_URL_PATH}")
    return url


def validate_response(response_text):
    """
    Validate the Telegram API response.
    Returns (success: bool, message_id: int|None, error: str|None).
    """
    try:
        if isinstance(response_text, dict):
            data = response_text
        else:
            text = response_text.strip()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                # web_get_contents wraps JSON in a search-result format
                # Try to find the Telegram JSON in the text
                start = text.find('{"ok"')
                if start == -1:
                    start = text.find('{"ok":')
                if start >= 0:
                    depth = 0
                    for i in range(start, len(text)):
                        if text[i] == '{':
                            depth += 1
                        elif text[i] == '}':
                            depth -= 1
                            if depth == 0:
                                data = json.loads(text[start:i+1])
                                break
                    else:
                        return False, None, f"Could not parse JSON from response: {text[:200]}"
                else:
                    return False, None, f"No JSON found in response: {text[:200]}"

        if not data.get("ok"):
            error_desc = data.get("description", "unknown error")
            error_code = data.get("error_code", "?")
            return False, None, f"Telegram API error: code={error_code}, desc={error_desc}"

        result = data.get("result", {})
        message_id = result.get("message_id")
        chat = result.get("chat", {})

        if message_id and chat.get("id") == int(CHAT_ID):
            return True, message_id, None

        return False, None, f"Unexpected response: {json.dumps(data)[:300]}"

    except Exception as e:
        return False, None, f"Validation error: {e}"


def log_delivery_result(success, message_id=None, error=None):
    """Log the delivery attempt result."""
    log = load_log()

    # If already delivered, don't overwrite (anti-duplicate)
    if log["status"] == "delivered" and log.get("message_id"):
        print(f"ALREADY DELIVERED: message_id={log['message_id']}")
        print("Not updating log. Message was already sent successfully.")
        return

    log["attempts"] = log.get("attempts", 0) + 1
    log["timestamp"] = now_ist()

    if success:
        log["status"] = "delivered"
        log["message_id"] = message_id
        log["last_error"] = None
        print(f"DELIVERY CONFIRMED: message_id={message_id}")
    else:
        log["status"] = "failed"
        log["last_error"] = error
        print(f"DELIVERY FAILED: {error}")
        print(f"Attempts so far: {log['attempts']}")

    save_log(log)


def check_status():
    """Print the current delivery status."""
    log = load_log()
    print(f"Delivery Status: {log['status'].upper()}")
    print(f"Date: {log.get('date', 'unknown')}")
    print(f"Message ID: {log.get('message_id', 'none')}")
    print(f"Attempts: {log.get('attempts', 0)}")
    print(f"Last Error: {log.get('last_error', 'none')}")
    print(f"Timestamp: {log.get('timestamp', 'unknown')}")
    return log


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python telegram_deliver.py --build "message text"')
        print('  python telegram_deliver.py --build --file /path/to/message.txt')
        print('  python telegram_deliver.py --validate \'{"ok":true,...}\'')
        print("  python telegram_deliver.py --check")
        print("  python telegram_deliver.py --reset")
        print("  python telegram_deliver.py --build-fallback")
        print("  python telegram_deliver.py --status-code")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--build":
        if len(sys.argv) > 2 and sys.argv[2] == "--file":
            with open(sys.argv[3]) as f:
                text = f.read()
        elif len(sys.argv) > 2:
            text = sys.argv[2]
        else:
            print("ERROR: No message text provided")
            sys.exit(1)
        build_url(text)

    elif cmd == "--build-fallback":
        build_fallback()

    elif cmd == "--validate":
        response_text = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        success, message_id, error = validate_response(response_text)
        log_delivery_result(success, message_id, error)
        if success:
            sys.exit(0)
        else:
            sys.exit(1)

    elif cmd == "--check":
        check_status()

    elif cmd == "--reset":
        reset_log()

    elif cmd == "--status-code":
        log = load_log()
        if log["status"] == "delivered":
            sys.exit(0)
        else:
            sys.exit(1)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
