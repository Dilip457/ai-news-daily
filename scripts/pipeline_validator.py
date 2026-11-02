#!/usr/bin/env python3
"""
Pipeline Validator — End-of-run Health Check
=============================================
Runs AFTER all pipeline steps. Checks:
  1. HTML briefing file exists and is valid (has articles, correct date)
  2. Telegram message was delivered today (checks the repo-format delivery log)

If Telegram delivery is missing:
  - Builds a fallback message from whatever data is available
  - Writes the retry URL to a private file for the agent to call via web_get_contents
    (the URL contains the bot token, so it is never printed)

Exit codes:
  0 = Everything passed (HTML exists, Telegram delivered)
  1 = Telegram not delivered — retry needed (see retry_url_path)
  2 = HTML missing — pipeline broken, needs manual intervention
  4 = Configuration error (telegram_deliver.py missing or credentials not set)

Usage:
  python pipeline_validator.py [--date YYYY-MM-DD]

Prints a JSON summary:
{
  "html_ok": true/false, "html_path": "...", "html_size": 12345, "html_date_ok": true/false,
  "telegram_status": "delivered|pending", "telegram_message_id": 89,
  "action_needed": "none|retry_telegram|fix_html|fix_config",
  "retry_url_path": "/scratch/work/telegram_retry_url.txt" (if retry needed)
}
"""

import json
import os
import re
import sys

AI_NEWS_HOME = os.environ.get("AI_NEWS_HOME", "/scratch/work/notes")
AI_NEWS_WORK = os.environ.get("AI_NEWS_WORK", "/scratch/work")
sys.path.insert(0, AI_NEWS_HOME)

try:
    import telegram_deliver as tg
except ImportError:
    tg = None


def check_html(date_str):
    """Check if the HTML briefing file exists and is valid."""
    path = os.path.join(AI_NEWS_WORK, f"ai-news-{date_str}.html")
    if not os.path.exists(path):
        return False, None, 0, False
    size = os.path.getsize(path)
    if size <= 10000:  # under 10KB cannot be a real briefing
        return False, path, size, False
    with open(path, encoding="utf-8") as f:
        content = f.read()
    has_content = "brief-item" in content or "brief-list" in content
    has_correct_date = f"<title>AI News Daily — {date_str}</title>" in content
    return has_content, path, size, has_correct_date


def build_retry_message(date_str):
    """Build a fallback Telegram message from available data."""
    saved = tg.message_save_path()
    if os.path.exists(saved):
        with open(saved, encoding="utf-8") as f:
            original = f.read()
        if date_str in original:
            return original

    analysis_path = os.path.join(AI_NEWS_WORK, "analysis_final.json")
    if os.path.exists(analysis_path):
        try:
            with open(analysis_path, encoding="utf-8") as f:
                data = json.load(f)
            articles = sorted(data.get("articles", []), key=lambda a: a.get("importance", 0), reverse=True)
            if articles:
                lines = [f"Today's AI News — {date_str}", "", f"Top story: {articles[0]['title']}", "", "Key updates:"]
                lines += [f"- {str(a['title'])[:80]}" for a in articles[1:6]]
                if data.get("concept_title"):
                    lines.append(f"\nConcept of the Day: {data['concept_title']}")
                lines.append(f"\nRead the full briefing:\n{tg.BRIEFING_LINK}")
                return "\n".join(lines)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    return (
        f"Today's AI News — {date_str}\n\n"
        "Today's AI briefing is now live.\n\n"
        f"Read it here:\n{tg.BRIEFING_LINK}"
    )


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--date":
        date_str = sys.argv[2]
    elif tg is not None:
        date_str = tg.today_str()
    else:
        date_str = None

    result = {
        "date": date_str,
        "html_ok": False,
        "html_path": None,
        "html_size": 0,
        "html_date_ok": False,
        "telegram_status": "pending",
        "telegram_message_id": None,
        "action_needed": "none",
        "retry_url_path": None,
    }

    if tg is None:
        result["action_needed"] = "fix_config"
        result["error"] = f"telegram_deliver.py not found in {AI_NEWS_HOME} (run bootstrap.py)"
        print(json.dumps(result, indent=2))
        sys.exit(4)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str or ""):
        print("Usage: python pipeline_validator.py [--date YYYY-MM-DD]")
        sys.exit(4)

    html_ok, html_path, html_size, date_ok = check_html(date_str)
    result.update(html_ok=html_ok, html_path=html_path, html_size=html_size, html_date_ok=date_ok)
    if not html_ok:
        result["action_needed"] = "fix_html"
        print(json.dumps(result, indent=2))
        sys.exit(2)

    entry = tg.delivery_for(date_str)
    if entry:
        result["telegram_status"] = "delivered"
        result["telegram_message_id"] = entry.get("message_id")
        print(json.dumps(result, indent=2))
        sys.exit(0)

    try:
        tg.build_url(build_retry_message(date_str), output_path=tg.fallback_url_path())
    except tg.ConfigError as e:
        result["action_needed"] = "fix_config"
        result["error"] = str(e)
        print(json.dumps(result, indent=2))
        sys.exit(4)

    result["action_needed"] = "retry_telegram"
    result["retry_url_path"] = tg.fallback_url_path()
    print("TELEGRAM NOT DELIVERED — RETRY NEEDED")
    print("Agent instructions:")
    print(f"  1. Read {tg.fallback_url_path()} (contains the bot token: never print or log it)")
    print("  2. Call web_get_contents with that URL")
    print(f"  3. Then run: python3 {os.path.join(AI_NEWS_HOME, 'telegram_deliver.py')} --validate '<response>'")
    print()
    print(json.dumps(result, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
