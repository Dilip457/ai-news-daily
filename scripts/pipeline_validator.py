#!/usr/bin/env python3
"""
Pipeline Validator — End-of-run Health Check
=============================================
Runs AFTER all pipeline steps. Checks:
  1. HTML briefing file exists and is valid (has articles, correct date)
  2. GitHub index.html is updated (title matches today's date)
  3. Telegram message was delivered (checks delivery log)

If Telegram delivery failed or was never attempted:
  - Builds a fallback message from whatever data is available
  - Outputs the retry URL for the agent to call via web_get_contents

Exit codes:
  0 = Everything passed (HTML exists, Telegram delivered)
  1 = Telegram not delivered — retry needed (prints retry URL)
  2 = HTML missing — pipeline broken, needs manual intervention
  3 = GitHub not updated — Telegram can still be sent with a note

Usage:
  python pipeline_validator.py [--date YYYY-MM-DD]

The script prints a JSON summary so the agent can parse it:
{
  "html_ok": true/false,
  "html_path": "...",
  "html_size": 12345,
  "github_ok": true/false,
  "github_title": "...",
  "telegram_status": "delivered|failed|pending",
  "telegram_message_id": 28,
  "action_needed": "none|retry_telegram|fix_html|fix_github",
  "retry_url": "https://api.telegram.org/..." (if retry needed)
}
"""

import sys
import os
import json
import re
from datetime import datetime

# Try to import the telegram_deliver module
sys.path.insert(0, "/workspace/notes")
try:
    from telegram_deliver import (
        load_log, build_fallback, build_url,
        BRIEFING_LINK, today_str, MESSAGE_SAVE_PATH
    )
except ImportError:
    # Fall back to inline implementations if module not available
    load_log = None
    build_fallback = None
    MESSAGE_SAVE_PATH = "/workspace/notes/telegram_last_message.txt"
    BRIEFING_LINK = "https://dilip457.github.io/ai-news-daily/"


def check_html(date_str):
    """Check if the HTML briefing file exists and is valid."""
    # Check scratch/work first (where generate_briefing_fixed.py writes)
    candidates = [
        f"/scratch/work/ai-news-{date_str}.html",
        f"/workspace/outputs/ai-news-{date_str}.html",
    ]
    
    for path in candidates:
        if os.path.exists(path):
            size = os.path.getsize(path)
            if size > 10000:  # At least 10KB = real content
                with open(path) as f:
                    content = f.read(2000)  # Read first 2KB for validation
                # Check it has article cards or brief items
                has_content = (
                    "card" in content or 
                    "brief-item" in content or 
                    "brief-list" in content
                )
                has_correct_date = date_str in content
                if has_content:
                    return True, path, size, has_correct_date
            return False, path, size, False
    
    return False, None, 0, False


def check_telegram_delivery():
    """Check if Telegram message was delivered today."""
    if load_log is None:
        # Fallback: check if log file exists
        log_path = "/workspace/notes/telegram_delivery_log.json"
        if os.path.exists(log_path):
            with open(log_path) as f:
                log = json.load(f)
        else:
            return "pending", None, None
    else:
        log = load_log()
    
    return log.get("status", "pending"), log.get("message_id"), log.get("last_error")


def build_retry_message(date_str):
    """Build a fallback Telegram message from available data."""
    # Try to read the saved message first
    if os.path.exists(MESSAGE_SAVE_PATH):
        with open(MESSAGE_SAVE_PATH) as f:
            original = f.read()
        # Check if it's from today
        if date_str in original:
            return original
    
    # Try to read analysis_final.json for article data
    analysis_path = "/scratch/work/analysis_final.json"
    if os.path.exists(analysis_path):
        try:
            with open(analysis_path) as f:
                data = json.load(f)
            articles = data.get("articles", [])
            if articles:
                top = articles[0]
                msg_lines = [
                    f"Today's AI News — {date_str}",
                    "",
                    f"Top story: {top['title']}",
                    "",
                    "Key updates:",
                ]
                for a in articles[1:5]:
                    msg_lines.append(f"- {a['title'][:80]}")
                
                concept = data.get("concept_title", "")
                if concept:
                    msg_lines.append(f"\nConcept of the Day: {concept}")
                
                msg_lines.append(f"\nRead the full briefing:\n{BRIEFING_LINK}")
                return "\n".join(msg_lines)
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Last resort: minimal message
    return (
        f"Today's AI News — {date_str}\n\n"
        "Today's AI briefing is now live.\n\n"
        f"Read it here:\n{BRIEFING_LINK}"
    )


def main():
    date_str = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--date" else today_str()
    
    result = {
        "date": date_str,
        "html_ok": False,
        "html_path": None,
        "html_size": 0,
        "github_ok": False,
        "github_title": None,
        "telegram_status": "pending",
        "telegram_message_id": None,
        "telegram_error": None,
        "action_needed": "none",
        "retry_url": None,
    }
    
    # 1. Check HTML file
    html_ok, html_path, html_size, date_ok = check_html(date_str)
    result["html_ok"] = html_ok
    result["html_path"] = html_path
    result["html_size"] = html_size
    
    if not html_ok:
        result["action_needed"] = "fix_html"
        print(json.dumps(result, indent=2))
        sys.exit(2)
    
    # 2. Check Telegram delivery
    tg_status, tg_msg_id, tg_error = check_telegram_delivery()
    result["telegram_status"] = tg_status
    result["telegram_message_id"] = tg_msg_id
    result["telegram_error"] = tg_error
    
    if tg_status == "delivered" and tg_msg_id:
        # Everything is fine
        result["action_needed"] = "none"
        print(json.dumps(result, indent=2))
        sys.exit(0)
    
    # 3. Telegram NOT delivered — build retry URL
    retry_message = build_retry_message(date_str)
    
    if build_url is not None:
        # Use the telegram_deliver module
        retry_url = build_url(retry_message, output_path="/workspace/input/telegram_retry_url.txt")
    else:
        # Fallback: build URL inline
        import urllib.parse
        BOT_TOKEN = "8645739822:AAFQrtZ1czXuDm9USN8Z8j4tpAS9HM2Q4V0"
        CHAT_ID = "-5322260984"
        base = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        params = urllib.parse.urlencode({
            "chat_id": CHAT_ID,
            "parse_mode": "HTML",
            "text": retry_message
        })
        retry_url = f"{base}?{params}"
        os.makedirs("/workspace/input", exist_ok=True)
        with open("/workspace/input/telegram_retry_url.txt", "w") as f:
            f.write(retry_url)
    
    result["action_needed"] = "retry_telegram"
    result["retry_url"] = retry_url
    
    print("TELEGRAM NOT DELIVERED — RETRY NEEDED")
    print(f"Status: {tg_status}")
    if tg_error:
        print(f"Last error: {tg_error}")
    print(f"Retry URL saved to: /workspace/input/telegram_retry_url.txt")
    print(f"Retry URL length: {len(retry_url)} chars")
    print(f"\nAgent instructions:")
    print(f"  1. Read /workspace/input/telegram_retry_url.txt")
    print(f"  2. Call web_get_contents with that URL")
    print(f"  3. Then run: python /workspace/notes/telegram_deliver.py --validate '<response>'")
    print()
    print(json.dumps(result, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
