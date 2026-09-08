# AI News Daily — Agentic Architecture & Workflow

## Overview

An autonomous agent that runs daily at 6:00 AM IST, fetches fresh AI news
from the web, deduplicates across three layers, scores and categorizes each
story using rule-based logic (no LLM), generates a magazine-grade HTML
briefing from a **locked, approved template** (Three.js morphing particles,
glassmorphism, spotlight hover, aurora background, dark/light toggle),
validates the output against the template at the byte level, pushes it to
GitHub Pages, delivers a summary to a Telegram group, and runs a final
self-healing validation pass that retries any failed step automatically.

---

## Pipeline at a Glance (v3 — September 2026)

```
[6 AM IST Cron Trigger]
        |
        v
[1. Collect]   -- 5 parallel web_search queries --> 25-40 raw articles
        |
        v
[2. Dedup]     -- 3-layer filter (exact / fuzzy / semantic) --> ~25 unique
        |
        v
[3. Generate]  -- generate_briefing_fixed.py + master_template.html --> 176KB HTML
        |          (swaps ONLY dynamic content; CSS/JS/layout are byte-locked)
        |
        v
[3d. Validate] -- template_validator.py --> 32 markers + CSS/JS byte comparison
        |          (exit 0 = safe to publish | exit 1 = WRONG TEMPLATE, block)
        |
        v
[4. Telegram]  -- web_get_contents → Bot API sendMessage --> "Daily AI news" group
        |          (BEFORE GitHub push so message goes out even if deploy fails)
        |
        v
[5. Deploy]    -- gzip+base64 → GitHub blob/tree/commit → deploy.yml → GitHub Pages
        |          (15-minute timeout; if it fails, Telegram already delivered)
        |
        v
[6. Validate]  -- pipeline_validator.py --> checks HTML exists + Telegram delivered
        |          (exit 0 = all good | exit 1 = retry Telegram | exit 2 = HTML missing)
        |
        v
[7. Deliver]   -- workspace_emit + present_output --> HTML file in chat
```

---

## Key Changes from v1 to v3 (September 2026)

| Area | v1 (August 2026) | v3 (September 2026) |
|------|-------------------|----------------------|
| HTML generation | generate_briefing_v5.py (41KB) — agent could rewrite freely | generate_briefing_fixed.py (18KB) — reads locked template, swaps only content |
| Template | Not stored; agent regenerated each run | master_template.html (194KB) stored locally + compressed on GitHub |
| Template enforcement | None | template_validator.py — 32 required markers, 60 forbidden markers, byte-level CSS/JS comparison |
| Pipeline order | Telegram was LAST (Step 6) — agent got stuck on GitHub deploy, never reached it | Telegram is Step 4 (BEFORE GitHub) — message always goes out |
| Telegram delivery | One-shot, no tracking | telegram_deliver.py — persistent log, anti-duplicate, retry fallback |
| Self-healing | None | pipeline_validator.py — checks HTML + Telegram at end, auto-builds retry URL |
| Fonts | Inter + Instrument Serif + JetBrains Mono | Inter + Instrument Serif only (JetBrains Mono was in the wrong template) |
| Accent color | Drifted to #0891b2 (teal) | Locked to #7c3aed (purple) |
| Background | Drifted to #0a0a0f | Locked to #070710 |
| Runtime | ~15 min (but could stretch to 71 min on deploy stuck) | ~15 min target, 15-min cap on GitHub step |

---

## Key Metrics

| Metric | Value |
|--------------------|--------------------------------|
| Daily trigger | 6:00 AM IST (cron 0 6 * * *) |
| Articles collected | 25-40 raw, ~25 after dedup |
| Dedup layers | 3 (exact, fuzzy, semantic) |
| LLM calls | 0 (fully rule-based) |
| Runtime target | ~15 minutes |
| Output size | ~176KB HTML (template-locked) |
| Template size | 194KB master (26KB compressed on GitHub) |
| Paid APIs | None |
| Validation checks | 32 required + 60 forbidden markers + byte-level CSS/JS |

---

## Step 1: Trigger and Scheduling

A cron job fires at 0 6 * * * (6:00 AM IST, Asia/Kolkata timezone)
every day. The platform spawns a fresh agent session with the pipeline
prompt — a self-contained instruction set covering collection, dedup,
template-locked HTML generation, validation, Telegram delivery, GitHub
deploy, and final self-healing validation.

The prompt explicitly lists the approved template's exact colors, class
names, canvas IDs, and fonts so the agent cannot drift even if it ignores
the scripts.

---

## Step 2: Data Collection

Five web_search queries run in parallel to maximize coverage. Each
returns results that are normalized to the Article schema.

### Search Queries

```
web_search("AI news today")
web_search("LLM model release")
web_search("OpenAI Anthropic Google AI news")
web_search("arxiv AI machine learning papers")
web_search("Hacker News AI")
```

### Article Schema

Each raw hit is normalized into:

```json
{
  "title":         "string",
  "url":           "string",
  "source":        "string",
  "summary":       "string (2-3 sentences, extracted from snippets)",
  "published_at":  "ISO date",
  "fetched_at":    "ISO date",
  "tags":          ["string"]
}
```

No LLM is used — summaries are extracted from search result snippets
and page metadata. Typically collects 25-40 raw articles per run.

---

## Step 3: Three-Layer Deduplication

Stories appearing across multiple sources are filtered through three
sequential layers. Each layer is progressively more expensive but catches
different types of duplicates.

```
Raw articles (25-40)
    |
    +---> [Layer 1: Exact]    SHA-256(normalized_title + url)
    |                          Catches syndicated reposts, URL variants
    |
    +---> [Layer 2: Fuzzy]    Levenshtein similarity > 85% on titles
    |                          Keeps the richer item (longer summary)
    |
    +---> [Layer 3: Semantic] Keyword-based topic clustering
                               Groups near-dupes from different sources
    |
    v
~25 unique articles
```

---

## Step 4: Analysis and Scoring

No LLM is used for analysis. All scoring is rule-based — keyword
matching against the title + summary determines category, importance,
and the "why it matters" hook.

### Categorization

Six categories assigned by keyword matching:

```
LLM        -> "model", "weights", "MoE", "parameters", "fine-tune"
Research   -> "paper", "arxiv", "benchmark", "method", "framework"
Safety     -> "safety", "breach", "attack", "rogue", "vulnerability"
Industry   -> "funding", "acquisition", "deal", "valuation", "policy"
Tools      -> "api", "sdk", "platform", "framework", "ide"
Robotics   -> "robot", "embodied", "physical", "manipulation"
```

### Importance Score (1-10)

Keyword-weighted scoring:

```
"breach" / "attack"      -> +3
"AGI"                    -> +3
"open-source" / "weights" -> +2
"benchmark" / "outperform" -> +2
"agent" / "agentic"      -> +2
"India" / "Indian"       -> +1
Base                     -> 5
Capped at 10
```

### why_it_matters

Keyword-driven hooks generated for each article:

```
if "open weight"  -> "you can download and self-host, avoiding vendor lock-in"
if "safety"       -> "has real security implications for your threat model"
if "benchmark"    -> "changes which model you should consider for your stack"
if "agent"        -> "pushes forward agentic AI capabilities"
if "India"        -> "directly relevant to the Indian AI ecosystem"
if "cost"         -> "impacts your API spend and inference budget"
```

### Editorial Content

- 5-paragraph briefing naming sources, covering top stories, model
  releases, research themes, and a closing summary
- 5 emerging trends by grouping related stories into trend cards
- Concept of the Day — 5-7 paragraphs of educational content about
  a concept relevant to that day's top stories, with em tags for key terms
- why_read — a dynamic paragraph identifying themes from top stories

### Output: analysis_final.json

All data is saved to /scratch/work/analysis_final.json with fields for
articles, trends, stats, why_read, concept_title, concept_subtitle,
concept_paras, and briefing_paragraphs.

---

## Step 5: HTML Generation (Template-Locked)

### The Problem This Solves

In v1, the agent wrote its own HTML from scratch each run. It drifted:
different colors (#0a0a0f instead of #070710), different class names
(.hero-title instead of .title), different Three.js (rewritten 12.5KB
instead of the original 4.8KB), missing features (grid-bg, kicker,
spotlight, modals, noise texture, bento grid). By September 2026 the live
site had entirely lost the approved design.

### The Fix: Three-Layer Template Lock

**Layer 1 — Master Template (static file)**

master_template.html (194KB) is a byte-exact copy of the user-approved
HTML from August 29, 2026. It contains:
- CSS variables: --bg:#070710, --accent:#7c3aed, --text:#edecf5, etc.
- Three.js morphing particles: canvas id bg-canvas, 5000 particles, 5 shapes
- Glassmorphism: backdrop-filter:blur(20px)
- Spotlight hover, aurora background, noise texture, grid-bg overlay
- Bento grid, click-to-open modals, expandable trend cards
- Top 10 with target="_blank" Open buttons, search + filter chips
- Kicker with live dot, subtitle, meta-row
- Dark/light theme toggle with toggleTheme()
- 177 CSS rules, 3 script blocks (4,816 + 4,839 chars)

A compressed copy (gzip+base64, 26KB) is stored on GitHub at
master_template.html.gz.b64 so the cron agent can restore it if the
local file is missing.

**Layer 2 — Build Script (content swap only)**

generate_briefing_fixed.py (18KB) reads the master template and swaps
ONLY dynamic content: title date, meta-row, tab labels, why-read paragraph,
stat counters, briefing heading date, glance count, brief-list items,
concept title/subtitle/paragraphs, Top 10 cards, filter chips, All Articles
cards, and trend cards.

The script does NOT touch the style block, script blocks, head structure,
or any CSS/JS. It self-validates 14 required markers before and after
content swap — if any are missing, it exits with code 1 and refuses to
produce output.

**Layer 3 — Strict Template Validator**

template_validator.py (9KB) runs AFTER the build script and performs:
1. 32 required markers check (exact CSS values, class names, JS features)
2. 60+ forbidden markers check (wrong template class names and variables)
3. Byte-level style block comparison against master template
4. Byte-level script block comparison against master template
5. Head structure check (Three.js src and Google Fonts URL)

Exit codes: 0 = safe to publish, 1 = wrong template, DO NOT PUBLISH.

### Template Recovery

If local files are missing, the cron prompt instructs the agent to
download them from GitHub:
- master_template.html.gz.b64 → base64 decode → gunzip → restore
- scripts/generate_briefing_fixed.py → restore
- scripts/template_validator.py → restore

---

## Step 6: Telegram Delivery (Before GitHub Push)

### Why Telegram Runs Before GitHub

In v1, Telegram was the LAST step. The agent frequently got stuck on
GitHub deploy validation (60+ minutes), never reaching the Telegram step.
Moving Telegram to Step 4 ensures the message always goes out, even if
the GitHub push fails entirely.

### How It Works

The sandbox blocks direct HTTP requests. All Telegram API calls go
through the web_get_contents MCP tool.

### Anti-Duplicate Protection

telegram_deliver.py (10.6KB) maintains a persistent delivery log at
/workspace/notes/telegram_delivery_log.json. Once the log says "delivered"
with a message_id, subsequent calls refuse to overwrite. Commands:
--reset, --build, --validate, --check, --build-fallback.

### Bot Details

- Bot token: 8645739822:AAFQrtZ1czXuDm9USN8Z8j4tpAS9HM2Q4V0
- Chat ID: -5322260984
- Bot name: AI News Daily (@Get_Excite_AI_News_bot)
- Group: "Daily AI news"

---

## Step 7: GitHub Deployment

The ~176KB HTML is too large for inline GitHub API calls. A
gzip + base64 + workflow approach compresses it to ~29KB, pushes
it as data.gz.b64, and a GitHub Action decompresses it into index.html.

### Push Sequence (Git Data API)

1. execute_code: gzip compress (level 9), base64 encode, save to file
2. delegate_task with inherit_parent_mcps=true:
   a. GITHUB_CREATE_A_BLOB → blob SHA
   b. GITHUB_GET_A_COMMIT → current HEAD commit SHA + tree SHA
   c. GITHUB_CREATE_A_TREE → new tree with data.gz.b64 entry
   d. GITHUB_CREATE_A_COMMIT → new commit on top of HEAD
   e. GITHUB_UPDATE_A_REFERENCE → move heads/main to new commit
3. deploy.yml workflow auto-triggers on push to data.gz.b64 path

### deploy.yml Workflow

Decodes base64, gunzips, commits index.html, removes data.gz.b64, pushes.

### Timeout

The GitHub push has a 15-minute timeout. If it fails, the Telegram
message is already delivered. The failure is logged and the pipeline
continues to validation.

---

## Step 8: Final Validation and Self-Healing

pipeline_validator.py (7.8KB) runs as the mandatory final step:
- Exit 0: HTML exists and Telegram delivered — pipeline complete
- Exit 1: Telegram NOT delivered — builds retry URL, sends via web_get_contents
- Exit 2: HTML file missing — pipeline broken, report failure

### Retry Fallback Chain

If Telegram failed, the validator builds a retry message from:
1. analysis_final.json article data (top stories)
2. telegram_last_message.txt (saved from original build)
3. Minimal "briefing is live" message with just the link

---

## Step 9: Chat Delivery

The HTML file is promoted to a workspace artifact via workspace_emit
and delivered to the user via present_output.

---

## File Inventory

### Durable Files (/workspace/notes/ — persists across sessions)

| File | Size | Purpose |
|------|------|---------|
| master_template.html | 194KB | Byte-exact approved template; CSS/JS never modified |
| generate_briefing_fixed.py | 18KB | Reads template, swaps only dynamic content, self-validates 14 markers |
| template_validator.py | 9KB | Validates output: 32 required + 60 forbidden markers + byte-level CSS/JS comparison |
| telegram_deliver.py | 11KB | Telegram delivery with persistent log, anti-duplicate, retry fallback |
| pipeline_validator.py | 8KB | End-of-run health check; retries failed Telegram, checks HTML exists |

### GitHub Repo (Dilip457/ai-news-daily)

| Path | Purpose |
|------|---------|
| index.html | Live GitHub Pages content (176KB) |
| master_template.html.gz.b64 | Compressed template backup (26KB) |
| scripts/generate_briefing_fixed.py | Build script backup |
| scripts/template_validator.py | Validator backup |
| scripts/telegram_deliver.py | Telegram delivery backup |
| scripts/pipeline_validator.py | Pipeline validator backup |
| .github/workflows/deploy.yml | Auto-decode workflow |
| .nojekyll | Bypass Jekyll for raw HTML |

---

## Approved Template Specification

### CSS Variables (Dark Theme — default)

```
--bg: #070710
--bg2: #0c0c18
--surface: rgba(255,255,255,.025)
--surface-h: rgba(255,255,255,.055)
--border: rgba(255,255,255,.06)
--border-h: rgba(255,255,255,.14)
--text: #edecf5
--muted: #8389a3
--dim: #4a4f64
--accent: #7c3aed
--accent2: #0891b2
--accent3: #db2777
--modal-bg: rgba(7,7,16,.95)
--modal-card: #0c0c18
--shadow: 0 20px 60px rgba(0,0,0,.5)
```

### Fonts

Inter (wght 300-800) + Instrument Serif (ital 0-1) from Google Fonts.

### Three.js

Source: cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js
Canvas ID: bg-canvas | Particles: 5000 | Morphing shapes: 5

### Key Class Names

.wrap, .kicker, .subtitle, .meta-row, .tabs, .tab-body, .bento,
.brief-list, .brief-item, .concept, .concept-label, .briefing-box,
.grid-cards, .card, .spotlight, .card-h, .card-sum, .card-why,
.trend, .trend-h, .trend-d, .trend-stories, .trend-expand,
.top10, .rank, .open-link-btn, .read-more-btn, .chips, .chip,
.search, .grid-bg, .noise, .aurora, .modal-card, .modal-why,
.theme-toggle, .reveal, .sec-head, .divider

### Key Animations

@keyframes drift (aurora), @keyframes fadeUp (reveal), @keyframes blink (live dot)

---

## Design Principles

1. No LLM for pipeline logic — all rule-based keyword matching.
2. Template is immutable — only dynamic content is swapped; CSS/JS byte-locked.
3. Telegram first, GitHub second — message always reaches the group.
4. Self-healing — final validation catches and retries failed steps.
5. Idempotent and safe — re-runs update, not duplicate; anti-duplicate log.
6. Honest about gaps — never fabricate; publish "No new AI updates today" if empty.
7. Recoverable — all scripts and template backed up on GitHub.

---

## Tech Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Scheduler | Cron 0 6 * * * | Daily 6 AM IST trigger |
| Agent Runtime | Sarvam AI sandbox | Python 3.12, Node 20, ephemeral |
| News Sources | web_search MCP | 5 parallel queries |
| Dedup | SHA-256 + Levenshtein + keyword clustering | 3-layer filter |
| HTML Engine | generate_briefing_fixed.py | Reads locked template, swaps content |
| Template Lock | template_validator.py | 32 markers + byte-level CSS/JS comparison |
| 3D Visuals | Three.js r128 (cdnjs) | 5000 particles, 5 morphing shapes |
| Fonts | Inter + Instrument Serif | Google Fonts |
| Telegram | telegram_deliver.py + web_get_contents | Bot API, persistent log, anti-duplicate |
| Self-Healing | pipeline_validator.py | End-of-run health check + retry |
| GitHub Push | Git Data API (blob/tree/commit/ref) | 5-call chain via sub-agent |
| Deploy | deploy.yml GitHub Action | base64 decode, gunzip, commit, push |
| Hosting | GitHub Pages | https://dilip457.github.io/ai-news-daily/ |

---

## Known Limitations and Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cron agent ignores scripts and writes own HTML | Wrong template, broken UI | Prompt lists exact colors/classes; validator blocks wrong output |
| Sandbox restart loses /workspace/notes/ | Scripts and template missing | All files backed up on GitHub; prompt has download instructions |
| Sub-agent cant see parents /workspace/ | Large file push fails | Files passed via delegate_task files parameter |
| read_file truncates at 2000 chars | Sub-agent cant read large files | Instructed to use execute_code with open() instead |
| GitHub deploy.yml has intermittent push conflicts | Deploy fails | Telegram already sent; 15-min timeout; can re-trigger manually |
| Sandbox blocks direct HTTP (403 tunnel) | Cant call Telegram/GitHub directly | All API calls go through web_get_contents MCP tool |
