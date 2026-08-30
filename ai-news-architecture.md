# AI News Daily — Agentic Architecture & Workflow

## Overview

An autonomous agent that runs daily at 6:00 AM IST, fetches fresh AI news
from the web, deduplicates across three layers, scores and categorizes each
story, generates a magazine-grade HTML briefing with Three.js morphing
particle visuals, pushes it to GitHub Pages, and delivers the link to a
Telegram group — all without human intervention.

---

## Pipeline at a Glance

```
[6 AM IST Cron Trigger]
        |
        v
[1. Collect] -- 5 parallel web_search queries --> 25-40 raw articles
        |
        v
[2. Dedup] -- 3-layer filter (exact / fuzzy / semantic) --> ~25 unique
        |
        v
[3. Analyze] -- categorize, score 1-10, why_it_matters, briefing, trends, concept
        |
        v
[4. Generate] -- build script --> 194KB self-contained HTML (Three.js + glassmorphism)
        |
        v
[5. Deploy] -- gzip+base64 --> GitHub blob/tree/commit --> deploy.yml workflow --> GitHub Pages
        |
        v
[6. Deliver] -- Telegram Bot API sendMessage --> "Daily AI news" group
```

---

## Key Metrics

| Metric             | Value                          |
|--------------------|--------------------------------|
| Daily trigger      | 6:00 AM IST (cron `0 6 * * *`) |
| Articles collected | 25-40 raw, ~25 after dedup     |
| Dedup layers       | 3 (exact, fuzzy, semantic)     |
| LLM calls          | 0 (fully rule-based)           |
| Runtime            | ~15 minutes                    |
| Output size        | 194KB HTML                     |
| Paid APIs          | None                           |

---

## Step 1: Trigger & Scheduling

A cron job fires at `0 6 * * *` (6:00 AM IST, Asia/Kolkata timezone)
every day. The platform spawns a fresh agent session with the pipeline
prompt — a self-contained instruction set covering collection, dedup,
HTML generation, GitHub deploy, and Telegram delivery.

The 6 AM start ensures the Telegram message arrives before 7 AM, even
with the ~15 minute pipeline runtime.

```
Cron Scheduler (6 AM IST)
    |
    v
Agent Runtime (Sarvam AI sandbox)
    Python 3.12, Node 20, ephemeral per session
```

---

## Step 2: Data Collection

Five `web_search` queries run in parallel to maximize coverage. Each
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

```
{
  title:         string
  url:           string
  source:        string       // e.g. "Forbes", "arXiv cs.AI"
  summary:       string       // 2-3 sentences, extracted from snippets
  published_at:  ISO date
  fetched_at:    ISO date
  tags:          string[]
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

### Persistent Store

`seen_articles.db` (SQLite) is committed to the GitHub repo. It stores
SHA-256 hashes of previously published articles to prevent re-publishing
the same story across days. Always committed back after each run.

---

## Step 4: Analysis & Scoring

No LLM is used for analysis. All scoring is **rule-based** — keyword
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
if "benchmark"    -> "changes which model you should consider"
if "agent"        -> "pushes forward agentic AI capabilities"
if "India"        -> "directly relevant to the Indian AI ecosystem"
if "cost"         -> "impacts your API spend and inference budget"
```

### Editorial Content

- **5-paragraph briefing** naming sources, covering top stories, model
  releases, research themes, and a closing summary
- **5 emerging trends** by grouping related stories into trend cards
- **Concept of the Day** — 5-7 paragraphs of educational content about
  a concept relevant to that day's top stories

---

## Step 5: HTML Generation

The build script `/workspace/notes/generate_briefing_v5.py` (41KB) reads
the JSON data and produces a single self-contained HTML file (~194KB)
with all design elements inline — no external assets except CDN links.

### Design Elements

```
Three.js Morphing Particles
  - 5000 particles (2500 on mobile)
  - Morph between 5 shapes: Sphere -> TorusKnot -> Icosahedron -> Torus -> Dodecahedron
  - Lerp-based morph progress
  - Mouse parallax

Glassmorphism UI
  - backdrop-filter: blur(20px) on all cards
  - Bento grid layout (why-read spans 3 columns, 4 stat boxes)
  - Light/dark theme toggle with localStorage persistence
  - Aurora background (blurred radial gradient blobs)
  - Noise texture overlay (SVG fractalNoise)
  - Spotlight hover (radial gradient follows mouse via CSS variables)

Fonts
  - Inter (body), Instrument Serif italic (accents), JetBrains Mono (labels)

Interactive Features
  - Click-to-open modals for news briefs (full article details)
  - Expandable trend cards (click to show related stories)
  - Top 10 with target="_blank" open links (not copy buttons)
  - Client-side search + category filter chips
  - Animated counters (easeOutCubic)
  - Scroll reveal (IntersectionObserver)

Four Tabs
  1. Home — Why Read This Today, Today's News at a Glance (25 stories),
     Concept of the Day, editorial briefing
  2. Emerging Trends — 5 expandable trend cards
  3. Top 10 — gradient rank badges with open-in-new-tab links
  4. All Articles — search + category filter chips
```

---

## Step 6: GitHub Deployment

The 194KB HTML is too large for inline GitHub API calls. A
**gzip + base64 + workflow** approach compresses it to ~26KB, pushes
it as `data.gz.b64`, and a GitHub Action decompresses it into
`index.html`.

### Deployment Flow

```
194KB HTML
    |
    v
gzip (level 9) --> 26KB
    |
    v
base64 encode --> 35K chars
    |
    v
Save to /workspace/input/data_gz_b64.txt
    |
    v
delegate_task (with GitHub MCP) reads file:
    |
    +---> GITHUB_CREATE_A_BLOB (encoding="utf-8", content=base64 string)
    |         Returns: blob SHA
    |
    +---> GITHUB_GET_A_TREE (current HEAD)
    |         Returns: current tree SHA + commit SHA
    |
    +---> GITHUB_CREATE_A_TREE (base_tree + new entry: data.gz.b64 -> blob SHA)
    |         Returns: new tree SHA
    |
    +---> GITHUB_CREATE_A_COMMIT (tree + parent)
    |         Returns: new commit SHA
    |
    +---> GITHUB_UPDATE_A_REFERENCE (heads/main -> new commit)
              Pushes to main branch
    |
    v
deploy.yml GitHub Action triggers on push:
    |
    +---> base64 -d data.gz.b64 > index.html.gz
    +---> gunzip -f index.html.gz
    +---> git add index.html
    +---> git rm data.gz.b64
    +---> git commit -m "Deploy: full briefing HTML"
    +---> git push
    |
    v
GitHub Pages auto-deploys from main
Live at: https://dilip457.github.io/ai-news-daily/
```

### Why the Blob/Tree/Commit Chain?

`GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS` takes content as an inline
string parameter. At 35K chars, sub-agents may truncate the content
during transcription. The Git Data API approach (blob -> tree ->
commit -> reference) is more reliable because the blob is created
programmatically and referenced by SHA, not by inline content.

---

## Step 7: Telegram Delivery

A `GET` request to the Telegram Bot API sends a concise message to
the group.

```
GET https://api.telegram.org/bot<TOKEN>/sendMessage
    ?chat_id=-5322260984
    &parse_mode=HTML
    &text=<URL_ENCODED_MESSAGE>
```

### Message Format

```
Today's AI News — August 31, 2026

Top story: <headline + 1-line summary>

Key updates:
- <update 1>
- <update 2>
- <update 3>
- <update 4>

Concept of the Day: <concept name>

Read the full interactive briefing:
https://dilip457.github.io/ai-news-daily/
```

### Bot Details

```
Bot username:  @Get_Excite_AI_News_bot
Group name:    Daily AI news
Chat ID:       -5322260984
Delivery:      GET request via web_get_contents (no multipart POST)
```

---

## Design Principles

1. **No LLM for pipeline logic.** All scoring, categorization, and
   "why it matters" generation is rule-based (keyword matching).
   The only external calls are web_search (collection), GitHub API
   (deployment), and Telegram Bot API (delivery).

2. **Idempotent and safe.** A re-run on the same day updates the same
   HTML file rather than creating duplicates. The dedup store is the
   source of truth — always committed back.

3. **Be honest about gaps.** If a source is unreachable or an API
   errors after 3 retries, log it and continue. Never fabricate
   articles, titles, or summaries. If zero new articles are found,
   publish a page stating "No new AI updates today."

4. **Durable scripts.** The build script lives in `/workspace/notes/`
   which persists across sandbox restarts. `/scratch/work/` is
   ephemeral and dies with the pod.

---

## Durable Files

| File | Location | Purpose |
|------|----------|---------|
| `generate_briefing_v5.py` | `/workspace/notes/` | HTML build script (41KB), survives restarts |
| `curate.py` | `/workspace/notes/ai-news-daily/` | Standalone pipeline (58KB), alternative |
| `seen_articles.db` | GitHub repo | SQLite dedup store, committed after each run |
| `deploy.yml` | `.github/workflows/` | GitHub Action, handles base64 decode + gunzip |
| `data.gz.b64` | GitHub repo (ephemeral) | Compressed payload, consumed and removed by workflow |

---

## Tech Stack

| Component | Technology | Role |
|-----------|-----------|------|
| Scheduler | Cron `0 6 * * *` | Daily 6 AM IST trigger |
| Agent Runtime | Sarvam AI sandbox | Python 3.12, Node 20, ephemeral |
| News Sources | `web_search` MCP | 5 parallel queries |
| Dedup Store | SQLite | SHA-256 exact dedup, persisted in repo |
| HTML Engine | `generate_briefing_v5.py` | Python, 41KB -> 194KB HTML |
| 3D Visuals | Three.js r128 (cdnjs) | 5000 particles, 5 morphing shapes |
| Fonts | Inter, Instrument Serif, JetBrains Mono | Google Fonts |
| GitHub Push | Git Data API (blob/tree/commit/ref) | 4-call chain, no inline limit |
| Deploy | `deploy.yml` GitHub Action | base64 decode -> gunzip -> commit |
| Hosting | GitHub Pages | Public URL |
| Telegram | Bot API (sendMessage GET) | Group message delivery |

---

## GitHub Repo

```
Repo:     Dilip457/ai-news-daily (public)
URL:      https://github.com/Dilip457/ai-news-daily
Pages:    https://dilip457.github.io/ai-news-daily/
Owner:    Dilip457 (Dilip Sanjay J), Srikar459 (Srikar J) 
Branch:   main
```

---

## Cron Job

```
ID:         01M16E912SNSJE2ZSQQDMMZ8KT
Name:       AI News Daily Briefing
Schedule:   0 6 * * *
Timezone:   Asia/Kolkata
Delivery:   web (agent output delivered to chat)
Status:     enabled
```
