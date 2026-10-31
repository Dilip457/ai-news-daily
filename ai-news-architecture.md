# AI News Daily — Architecture (v4.1, September 2026)

## Design Principle

The GitHub repo `Dilip457/ai-news-daily` is the ONLY source of truth. Local workspaces can be wiped at any time — every run rebuilds itself from GitHub and verifies checksums. Three independent scheduled runs per day guarantee delivery: the news goes out even if one (or two) of them fail completely.

## Delivery Chain (all IST)

```
6:00 AM   Main briefing run (cron "AI News Daily Briefing")
              ↓ fails or never fires?
9:30 AM   Watchdog 1 — checks GitHub delivery log for today's date
              ↓ still not delivered?
5:30 PM   Watchdog 2 — final same-day recovery (same check + full run)
              ↓ still nothing? Telegram failure alert is sent
```

Watchdogs are stateless: they read `telegram_delivery_log.json` from the repo. If today's date is logged → exit silently. If not → run the full pipeline. The same anti-duplicate log check runs before every Telegram send, so multiple runs can never double-message.

## Pipeline (v4.1, identical for main run and watchdogs)

```
0. Bootstrap   curl bootstrap.py from GitHub if missing → run it
               (downloads all scripts + template + delivery log, verifies SHA-256
                against scripts/checksums.json; handles raw-gzip AND base64
                template backup formats; exit 1 = alert, do not proceed)
1. Collect     5× web_search (last 24h) → 15-25 unique articles
2. Build       analysis_final.json → generate_briefing_fixed.py
               (reads master_template.html, swaps ONLY dynamic content)
3. Validate    template_validator.py — exit 0 required to publish
4. Telegram    ONE message via Bot API (web_get_contents), anti-duplicate check
5. Record      append today's entry to telegram_delivery_log.json on GitHub
               (BEFORE the briefing push — avoids racing deploy.yml)
6. Publish     gzip+base64 HTML → split into 4 parts → blob/tree/commit/ref API,
               each part SHA-verified (sha1('blob <len>\0'+content))
               → deploy.yml assembles parts, commits index.html + updates/<DATE>.html,
               cleans up parts. If deploy fails → re-dispatch once via workflow_dispatch.
7. Alert       any step failing after retries → ONE Telegram failure alert.
               Never silent.
```

## What Changed (v3 → v4.1)

| Area | Before (v3) | Now (v4.1) |
|------|--------|-----|
| Trigger reliability | Single 6 AM cron (stalled silently for 7 days in Sept) | Main run + 2 staggered watchdogs (9:30 AM, 5:30 PM) with stateless delivery check |
| Workspace wipe recovery | Ad-hoc downloads, broken base64 template backup | bootstrap.py Step 0: verified SHA-256 restore of everything, auto-detects backup format |
| Big-file push | Single data.gz.b64 (corrupted in transit ≥3 times) | 4 SHA-verified chunks; blob API only (Contents API mangles base64-looking content) |
| Dedup state | Local log file (wiped with workspace) | telegram_delivery_log.json committed to the repo |
| Push race | Delivery log committed after deploy trigger → non-fast-forward failures | Log committed before the briefing push; briefing is the final commit |
| Failure mode | Silent until user noticed days later | Telegram failure alert from every failing run; watchdogs as backup executors |
| Deploy self-heal | None | Run re-dispatches deploy.yml once on failure |

## Repo Layout (source of truth)

| Path | Purpose |
|------|---------|
| `scripts/bootstrap.py` | Self-healing entry point: fetch + SHA-256 verify everything |
| `scripts/checksums.json` | SHA-256 manifest for all pipeline files |
| `scripts/generate_briefing_fixed.py` (18KB) | Template-locked HTML builder (swaps content only, self-validates) |
| `scripts/template_validator.py` (6KB) | 32 required + ~60 forbidden markers, byte-level CSS/JS diff — the publish gate |
| `scripts/telegram_deliver.py` (11KB) | Bot API delivery helper with log + retry |
| `scripts/pipeline_validator.py` (8KB) | End-of-run check: HTML + Telegram delivered |
| `master_template.html.gz.b64` | Approved template backup (raw gzip format — bootstrap auto-detects) |
| `telegram_delivery_log.json` | Dedup record: exactly one message per day |
| `data.gz.b64.part1..4` | Today's briefing chunks (cleaned up by deploy.yml after deploy) |
| `updates/<DATE>.html` | Permanent daily archive |
| `CRON_PROMPT.md` | Canonical pipeline prompt (v4.1) |
| `.github/workflows/deploy.yml` | Assembles parts → index.html → commit + push |

## Template Lock (unchanged)

The master template (194KB) is a byte-exact copy of the approved Aug 29 design. The build script swaps only: title date, meta-row, tab labels, why-read, stat counters, brief items, concept text, Top 10 cards, filter chips, all articles, trends. CSS, JS, layout, colors, fonts are never touched.

**Colors:** bg #070710, text #edecf5, accent #7c3aed (purple), accent2 #0891b2, accent3 #db2777; light: bg #f8f9fc, text #1a1a2e, accent #6d28d9.
**Fonts:** Inter (+ serif fallback). Three.js r128 from cdnjs, canvas id `bg-canvas`.
**Key classes:** .wrap .kicker .subtitle .meta-row .bento .brief-list .concept .grid-cards .card .spotlight .trend .chips .modal-card .grid-bg .noise .aurora .divider

## Telegram

Bot @Get_Excite_AI_News_bot → group "Daily AI news", sent via `web_get_contents` (sandbox blocks direct HTTP). Exactly one message per day, enforced by the repo-hosted delivery log. Failure alerts use the same channel — the user always hears something.

## Rules

- No LLM for pipeline logic — keyword-based scoring and extraction only
- Template is immutable — validator exit 1 blocks publishing
- Telegram before GitHub — the message always reaches the group
- Never fail silently — news, or a failure alert, every single day
- Never fabricate — publish "No new AI updates today" if nothing is found
- GitHub is the source of truth — every run bootstraps and verifies from it
- Runtime cap 25 min, no unbounded sleeps or infinite retries (prevents hung runs stalling the scheduler)
