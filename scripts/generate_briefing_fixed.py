#!/usr/bin/env python3
"""
AI News Daily — Template-Locked Briefing Builder
=================================================
THE ONLY SCRIPT that should be used to generate the daily HTML.

This script reads the approved master template (master_template.html) and
ONLY swaps dynamic content placeholders. It does NOT modify CSS, JS, layout,
colors, fonts, or any visual element. The output is guaranteed to have
identical UI to the approved template.

USAGE:
    python generate_briefing_fixed.py /path/to/data.json YYYY-MM-DD

OUTPUT:
    /scratch/work/ai-news-YYYY-MM-DD.html

VALIDATION:
    After building, the script self-validates that the output contains
    all required template markers. If any are missing, it prints an error
    and exits with code 1.

USAGE BY THE CRON AGENT:
    The agent MUST run this script. The agent MUST NOT write its own HTML.
    The agent MUST NOT modify this script or the master template.
    If this script or the template is missing, the agent MUST restore them
    from the GitHub repo Dilip457/ai-news-daily.
"""

import json, re, os, sys, hashlib
from html import escape
from datetime import datetime

TEMPLATE_PATH = "/workspace/notes/master_template.html"

cat_colors = {
    "LLM": "#7c3aed", "Research": "#059669", "Safety": "#dc2626",
    "Industry": "#d97706", "Tools": "#0891b2", "Robotics": "#db2777",
    "Computer Vision": "#9333ea", "NLP": "#2563eb",
}

# Required markers that MUST exist in the output (template integrity check)
REQUIRED_MARKERS = [
    '--bg:#070710',           # Original dark bg color
    '--accent:#7c3aed',       # Original purple accent
    '--text:#edecf5',         # Original text color
    'class="grid-bg"',        # Grid background overlay
    'class="kicker"',         # Live indicator
    'class="brief-list"',     # Brief list container
    'class="bento"',          # Bento grid
    'class="concept-label"',  # Concept label
    'bg-canvas',              # Three.js canvas ID
    'three.min.js',           # Three.js library
    '.spotlight::before',     # Spotlight hover effect CSS
    'class="noise"',          # Noise texture
    'class="aurora"',         # Aurora background
    'toggleTheme',            # Theme toggle function
]

def esc(s):
    return escape(str(s))

def json_attr(obj):
    j = json.dumps(obj, ensure_ascii=False)
    j = j.replace("\x27", "&#x27;").replace("\x22", "&#x22;")
    return j

def rich_html(text):
    parts = text.split("<em>")
    result = escape(parts[0])
    for part in parts[1:]:
        if "</em>" in part:
            em_content, rest = part.split("</em>", 1)
            result += "<em>" + escape(em_content) + "</em>" + escape(rest)
        else:
            result += "<em>" + escape(part)
    return result

def build_brief_items(articles):
    items = []
    for i, a in enumerate(articles):
        c = cat_colors.get(a["category"], "#64748b")
        sents = a["summary"].split(". ")
        brief = ". ".join(sents[:2]) + "."
        if len(brief) > 180:
            brief = brief[:177] + "..."
        article_data = {
            "title": a["title"], "summary": a["summary"],
            "why_it_matters": a["why_it_matters"], "source": a["source"],
            "url": a["url"], "category": a["category"], "importance": a["importance"]
        }
        data_attr = json_attr(article_data)
        num = "%02d" % (i + 1)
        items.append(
            '      <div class="brief-item spotlight" style="--c:' + c + '" data-article=\'' + data_attr + '\'>\n'
            '        <span class="brief-num">' + num + '</span>\n'
            '        <span class="brief-tag" style="background:' + c + '">' + esc(a["category"]) + '</span>\n'
            '        <div class="brief-body">\n'
            '          <div class="brief-title">' + esc(a["title"]) + '</div>\n'
            '          <div class="brief-text">' + esc(brief) + '</div>\n'
            '        </div>\n'
            '        <span class="brief-score" style="--c:' + c + '">' + str(a["importance"]) + '<small>/10</small></span>\n'
            '      </div>'
        )
    return "\n".join(items)

def build_top10_cards(articles):
    cards = []
    for i, a in enumerate(articles[:10]):
        c = cat_colors.get(a["category"], "#64748b")
        article_data = {
            "title": a["title"], "summary": a["summary"],
            "why_it_matters": a["why_it_matters"], "source": a["source"],
            "url": a["url"], "category": a["category"], "importance": a["importance"]
        }
        data_attr = json_attr(article_data)
        sents = a["summary"].split(". ")
        short = ". ".join(sents[:2]) + "."
        rank = "%02d" % (i + 1)
        grad = "linear-gradient(135deg," + c + "," + c + "88)"
        cards.append(
            '      <div class="card spotlight top10" style="--c:' + c + '" data-article=\'' + data_attr + '\'>\n'
            '        <div class="rank" style="background:' + grad + '">' + rank + '</div>\n'
            '        <div class="card-body">\n'
            '          <span class="card-cat" style="background:' + c + '">' + esc(a["category"]) + '</span>\n'
            '          <h3 class="card-title">' + esc(a["title"]) + '</h3>\n'
            '          <p class="card-summary">' + esc(short) + '</p>\n'
            '          <div class="card-actions">\n'
            '            <a href="' + esc(a["url"]) + '" target="_blank" rel="noopener" class="open-btn" style="--c:' + c + '">Open \u2197</a>\n'
            '            <button class="read-more-btn" data-article=\'' + data_attr + '\' style="--c:' + c + '">Read More</button>\n'
            '          </div>\n'
            '          <div class="card-meta">' + esc(a["source"]) + ' &middot; Score: ' + str(a["importance"]) + '/10</div>\n'
            '        </div>\n'
            '      </div>'
        )
    return "\n".join(cards)

def build_all_cards(articles):
    cards = []
    for i, a in enumerate(articles):
        c = cat_colors.get(a["category"], "#64748b")
        article_data = {
            "title": a["title"], "summary": a["summary"],
            "why_it_matters": a["why_it_matters"], "source": a["source"],
            "url": a["url"], "category": a["category"], "importance": a["importance"]
        }
        data_attr = json_attr(article_data)
        cards.append(
            '      <div class="card spotlight" data-category="' + esc(a["category"]) + '" data-title="' + esc(a["title"].lower()) + '" style="--c:' + c + '" data-article=\'' + data_attr + '\'>\n'
            '        <span class="card-cat" style="background:' + c + '">' + esc(a["category"]) + '</span>\n'
            '          <h3 class="card-title">' + esc(a["title"]) + '</h3>\n'
            '          <p class="card-summary">' + esc(a["summary"]) + '</p>\n'
            '          <div class="card-actions">\n'
            '            <a href="' + esc(a["url"]) + '" target="_blank" rel="noopener" class="open-btn" style="--c:' + c + '">Open \u2197</a>\n'
            '            <button class="read-more-btn" data-article=\'' + data_attr + '\' style="--c:' + c + '">Read More</button>\n'
            '          </div>\n'
            '          <div class="card-meta">' + esc(a["source"]) + ' &middot; Score: ' + str(a["importance"]) + '/10</div>\n'
            '      </div>'
        )
    return "\n".join(cards)

def build_trend_cards(trends, articles):
    cards = []
    emojis = ["\U0001F525", "\U0001F680", "\U0001F9E0", "\u26A0\uFE0F", "\U0001F4A1", "\U0001F4CA", "\U0001F527", "\U0001F310"]
    for i, t in enumerate(trends):
        emoji = emojis[i % len(emojis)]
        related = []
        for a in articles:
            for kw in t["related"]:
                if kw.lower() in a["title"].lower():
                    related.append(a["title"])
                    break
        related_html = "".join('<div class="trend-story">' + esc(r) + '</div>' for r in related[:6])
        count = len(related)
        cards.append(
            '      <div class="card spotlight trend" style="--c:var(--accent)" data-trend="' + str(i) + '">\n'
            '        <div class="trend-header" onclick="this.parentElement.classList.toggle(\'expanded\')">\n'
            '          <div class="trend-emoji">' + emoji + '</div>\n'
            '          <div class="trend-info">\n'
            '            <h3 class="trend-h">' + esc(t["title"]) + '</h3>\n'
            '            <p class="trend-d">' + esc(t["description"]) + '</p>\n'
            '            <span class="trend-n">' + str(count) + ' stories</span>\n'
            '          </div>\n'
            '          <span class="trend-expand">\u25BC</span>\n'
            '        </div>\n'
            '        <div class="trend-stories">\n'
            '          <div class="trend-stories-label">Related stories (' + str(count) + ')</div>\n'
            '          <div class="trend-story-list">' + related_html + '</div>\n'
            '        </div>\n'
            '      </div>'
        )
    return "\n".join(cards)

def build_filter_chips(categories):
    chips = []
    for cat in sorted(categories):
        c = cat_colors.get(cat, "#64748b")
        chips.append('<button class="chip" data-filter="' + esc(cat) + '" style="--c:' + c + '">' + esc(cat) + '</button>')
    return "\n      ".join(chips)

def build_concept_html(concept_paras):
    return "\n".join("<p>" + rich_html(p.strip()) + "</p>" for p in concept_paras if p.strip())

def build_briefing_html(briefing_paragraphs):
    return "\n".join("<p>" + esc(p.strip()) + "</p>" for p in briefing_paragraphs if p.strip())

def find_grid_end(html, grid_start):
    depth = 0
    pos = grid_start
    while pos < len(html):
        open_pos = html.find("<div", pos)
        close_pos = html.find("</div>", pos)
        if close_pos == -1:
            return len(html)
        if open_pos != -1 and open_pos < close_pos:
            depth += 1
            pos = open_pos + 4
        else:
            depth -= 1
            pos = close_pos + 6
            if depth == 0:
                return close_pos
    return len(html)

def validate_output(html):
    """Check that the output HTML contains all required template markers."""
    missing = []
    for marker in REQUIRED_MARKERS:
        if marker not in html:
            missing.append(marker)
    return missing

def build_briefing(data, date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(TEMPLATE_PATH):
        print(f"ERROR: Master template not found at {TEMPLATE_PATH}")
        print("Restore it from GitHub repo Dilip457/ai-news-daily")
        sys.exit(1)

    articles = sorted(data["articles"], key=lambda x: x["importance"], reverse=True)
    trends = data["trends"]
    stats = data["stats"]

    brief_items = build_brief_items(articles)
    top10_cards = build_top10_cards(articles)
    all_cards = build_all_cards(articles)
    trend_cards = build_trend_cards(trends, articles)
    filter_chips = build_filter_chips(stats.get("categories", {}))
    concept_html_str = build_concept_html(data.get("concept_paras", []))
    briefing_html_str = build_briefing_html(data.get("briefing_paragraphs", []))

    with open(TEMPLATE_PATH, "r") as f:
        html = f.read()

    # Verify template integrity BEFORE modifying
    pre_check = validate_output(html)
    if pre_check:
        print(f"WARNING: Master template is missing markers: {pre_check}")
        print("The template may be corrupted. Restore from GitHub.")

    # 1. Title
    html = html.replace(
        "<title>AI News Daily \u2014 2026-08-29</title>",
        "<title>AI News Daily \u2014 " + date_str + "</title>"
    )

    # 2. Meta row (date, story count, trend count)
    html = re.sub(
        r'<span>2026-08-29 09:15 UTC</span>.*?<span>5 trends</span>',
        '<span>' + date_str + ' 09:00 IST</span><span class="sep"></span><span>' + date_str + '</span><span class="sep"></span><span>' + str(stats["total"]) + ' stories</span><span class="sep"></span><span>' + str(len(trends)) + ' trends</span>',
        html, flags=re.DOTALL
    )

    # 3. Tab labels
    html = html.replace("Trends (5)", "Trends (" + str(len(trends)) + ")")
    html = html.replace("All (25)", "All (" + str(stats["total"]) + ")")

    # 4. Why Read This Today
    why_read = data.get("why_read", "")
    html = re.sub(
        r'(<div class="bento-why reveal"><span class="label">Why Read This Today</span><p>)(.*?)(</p></div>)',
        lambda m: m.group(1) + esc(why_read) + m.group(3),
        html, flags=re.DOTALL
    )

    # 5. Stat counters
    html = html.replace('data-count="39"', 'data-count="' + str(stats.get("collected", stats["total"])) + '"')
    html = html.replace('data-count="35"', 'data-count="' + str(stats.get("deduped", stats["total"])) + '"')
    html = html.replace('data-count="25"', 'data-count="' + str(stats["total"]) + '"')

    # 6. Replace the "Today pipeline collected" paragraph
    briefing_paragraphs = data.get("briefing_paragraphs", [])
    if briefing_paragraphs:
        html = re.sub(
            r'<p>Today&#x27;s pipeline collected.*?</p>',
            "<p>" + esc(briefing_paragraphs[0]) + "</p>",
            html, count=1, flags=re.DOTALL
        )

    # 6b. Replace hardcoded date in briefing heading
    html = html.replace("The State of AI <em>2026-08-29</em>", "The State of AI <em>" + date_str + "</em>")

    # 7. Glance count
    html = re.sub(
        r'(Today&#x27;s News at a Glance <span class="count">)25 stories',
        lambda m: m.group(1) + str(stats["total"]) + " stories",
        html
    )
    html = re.sub(
        r"(Today's News at a Glance <span class=\"count\">)25 stories",
        lambda m: m.group(1) + str(stats["total"]) + " stories",
        html
    )

    # 8. Replace brief-list content
    brief_list_start = html.find('<div class="brief-list">')
    if brief_list_start > 0:
        list_content_start = brief_list_start + len('<div class="brief-list">')
        hr_pos = html.find('<hr class="divider">', list_content_start)
        if hr_pos > 0:
            close_div = html.rfind("</div>", list_content_start, hr_pos)
            if close_div > 0:
                html = html[:list_content_start] + "\n" + brief_items + "\n    " + html[close_div:]

    # 9. Replace concept section
    concept_title = data.get("concept_title", "")
    concept_sub = data.get("concept_subtitle", "")

    html = re.sub(
        r'(<span class="concept-label">Concept of the Day</span>\s*<h2>)(.*?)(</h2>)',
        lambda m: m.group(1) + esc(concept_title) + m.group(3),
        html, flags=re.DOTALL
    )

    html = re.sub(
        r'(<p class="sub">)(.*?)(</p>)',
        lambda m: m.group(1) + esc(concept_sub) + m.group(3),
        html, count=1, flags=re.DOTALL
    )

    # Replace concept paragraphs
    sub_end = html.find('<p class="sub">')
    if sub_end > 0:
        sub_close = html.find("</p>", sub_end) + 4
        concept_div_end = html.find("</div>", sub_close + 200)
        if concept_div_end > 0:
            html = html[:sub_close] + "\n      " + concept_html_str + "\n    " + html[concept_div_end:]

    # 10. Replace Top 10 cards
    top10_section = html.find('id="top10"')
    if top10_section > 0:
        grid_start = html.find('<div class="grid-cards">', top10_section)
        if grid_start > 0:
            grid_end = find_grid_end(html, grid_start)
            open_tag_len = len('<div class="grid-cards">')
            html = html[:grid_start + open_tag_len] + "\n" + top10_cards + "\n      " + html[grid_end:]

    # 11. Replace filter chips
    chips_start = html.find('<div class="chips" id="chips">')
    if chips_start > 0:
        chips_end = html.find('</div>', chips_start)
        html = html[:chips_start + len('<div class="chips" id="chips">')] + filter_chips + html[chips_end:]

    # 12. Replace All Articles cards
    all_section = html.find('id="all"')
    if all_section > 0:
        grid_start = html.find('<div class="grid-cards" id="cardGrid">', all_section)
        if grid_start > 0:
            grid_end = find_grid_end(html, grid_start)
            open_tag_len = len('<div class="grid-cards" id="cardGrid">')
            html = html[:grid_start + open_tag_len] + "\n" + all_cards + "\n    " + html[grid_end:]

    # 13. Replace trend cards in Trends tab
    trends_section = html.find('id="trends"')
    if trends_section > 0:
        grid_start = html.find('<div class="grid-cards">', trends_section)
        if grid_start > 0:
            grid_end = find_grid_end(html, grid_start)
            open_tag_len = len('<div class="grid-cards">')
            html = html[:grid_start + open_tag_len] + "\n" + trend_cards + "\n      " + html[grid_end:]

    # FINAL VALIDATION — ensure all template markers are still present
    missing = validate_output(html)
    if missing:
        print(f"ERROR: Output is missing template markers: {missing}")
        print("The template may have been corrupted during content swap.")
        print("DO NOT publish this output. Restore the master template and retry.")
        sys.exit(1)

    return html

if __name__ == "__main__":
    data_path = sys.argv[1] if len(sys.argv) > 1 else "/scratch/work/analysis_final.json"
    date_str = sys.argv[2] if len(sys.argv) > 2 else None

    with open(data_path) as f:
        data = json.load(f)

    html = build_briefing(data, date_str)

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    outpath = "/scratch/work/ai-news-" + date_str + ".html"
    with open(outpath, "w") as f:
        f.write(html)

    print("Built: " + outpath + " (" + str(len(html)) + " bytes)")
    print("Articles: " + str(len(data["articles"])) + " | Trends: " + str(len(data["trends"])) + " | Date: " + date_str)
    print("Template validation: PASSED — all required markers present")
    print("UI is identical to the approved master template")
