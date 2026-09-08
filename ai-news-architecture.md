# AI News Daily — Architecture (v3, September 2026)

## Pipeline

```
6 AM IST Cron
    ↓
1. Collect     5× web_search → 25-40 raw articles
2. Dedup       SHA-256 → Levenshtein >85% → keyword cluster → ~25 unique
3. Generate    generate_briefing_fixed.py reads master_template.html, swaps ONLY content
3d. Validate   template_validator.py: 32 required + 60 forbidden markers + byte-level CSS/JS check
4. Telegram    web_get_contents → Bot API sendMessage (BEFORE GitHub, anti-duplicate log)
5. Deploy      gzip+base64 → GitHub blob/tree/commit → deploy.yml → Pages (15-min timeout)
6. Validate    pipeline_validator.py: checks HTML + Telegram, retries if failed
7. Deliver     workspace_emit → present_output
```

## What Changed (v1 → v3)

| Area | Before | Now |
|------|--------|-----|
| HTML build | Agent wrote own HTML, drifted every run | Script reads locked template, swaps only content |
| Template | Not stored | 194KB master file + 26KB compressed backup on GitHub |
| Enforcement | None | Validator: 32 required markers, 60 forbidden, byte-level CSS/JS diff |
| Pipeline order | Telegram last (agent got stuck on deploy, never reached it) | Telegram before GitHub (message always goes out) |
| Telegram | One-shot, no tracking | Persistent log, anti-duplicate, retry fallback |
| Self-healing | None | Final validator auto-retries failed Telegram |
| Colors | Drifted to teal #0891b2, bg #0a0a0f | Locked: accent #7c3aed, bg #070710 |

## Scripts (all in /workspace/notes/ and scripts/ on GitHub)

| Script | Purpose |
|--------|---------|
| `generate_briefing_fixed.py` (18KB) | Reads template, swaps dynamic content, self-validates 14 markers |
| `template_validator.py` (9KB) | 32 required + 60 forbidden markers, byte-level CSS/JS comparison |
| `telegram_deliver.py` (11KB) | Bot API delivery, persistent log, anti-duplicate, retry fallback |
| `pipeline_validator.py` (8KB) | End-of-run check: HTML exists + Telegram delivered, auto-retry |

## Template Lock

The master template (`master_template.html`, 194KB) is a byte-exact copy of the approved Aug 29 design. The build script swaps only: title date, meta-row, tab labels, why-read, stat counters, brief items, concept text, Top 10 cards, filter chips, all articles, trends. CSS, JS, layout, colors, fonts are never touched.

If local files are missing (sandbox restart), the agent downloads from GitHub:
- `master_template.html.gz.b64` → base64 decode → gunzip
- `scripts/*.py` → restore directly

## Approved Template Specs

**Colors (dark):** bg #070710, text #edecf5, accent #7c3aed (purple), accent2 #0891b2, accent3 #db2777
**Colors (light):** bg #f8f9fc, text #1a1a2e, accent #6d28d9
**Fonts:** Inter + Instrument Serif (no JetBrains Mono)
**Three.js:** r128 from cdnjs, canvas id `bg-canvas`, 5000 particles, 5 shapes
**Key classes:** .wrap .kicker .subtitle .meta-row .bento .brief-list .concept .grid-cards .card .spotlight .trend .chips .modal-card .grid-bg .noise .aurora .divider
**Effects:** backdrop-filter:blur(20px), spotlight hover, aurora drift, noise texture, dark/light toggle

## GitHub Deploy

HTML (~176KB) → gzip → base64 (~29KB) → `data.gz.b64` pushed via blob/tree/commit/ref API (sub-agent) → `deploy.yml` auto-triggers: base64 -d → gunzip → commit index.html → push.

## Telegram

Bot: @Get_Excite_AI_News_bot | Group: "Daily AI news" | Sent via `web_get_contents` (sandbox blocks direct HTTP). One message per run. Log at `/workspace/notes/telegram_delivery_log.json` prevents duplicates.

## Rules

- No LLM — all scoring/categorization is keyword-based
- Template is immutable — validator blocks wrong output from publishing
- Telegram before GitHub — message always reaches the group
- Self-healing — final step retries failures automatically
- Never fabricate — publish "No new AI updates today" if empty
- All scripts backed up on GitHub for sandbox restart recovery
