# ai-news-daily
Daily AI/LLM news briefing: curated, deduplicated and ranked automatically. Published via GitHub Pages at https://dilip457.github.io/ai-news-daily/ and summarized in a Telegram group.

A scheduled agent (prompt: [CRON_PROMPT.md](CRON_PROMPT.md)) collects the last 24h of AI news. It builds the page with the scripts in [scripts/](scripts/), sends one Telegram message, and pushes the page. The [deploy workflow](.github/workflows/deploy.yml) verifies and validates the page before it goes live.

- How it works: [ai-news-architecture.md](ai-news-architecture.md)
- Incidents and workarounds: [RUN_NOTES.md](RUN_NOTES.md)
- Threat model and owner checklist: [SECURITY.md](SECURITY.md)

Run the checks locally: `python3 scripts/repo_audit.py && python3 -m unittest discover -s tests -v`
