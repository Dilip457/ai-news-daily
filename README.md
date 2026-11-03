# ai-news-daily

A daily AI/LLM news briefing: curated, deduplicated and ranked by an AI agent every morning at 6:00 AM IST. It's published at **https://dilip457.github.io/ai-news-daily/** and summarized in the Telegram group "Daily AI news".

## How it works

A scheduled agent on Sarvam Cowork collects the last 24 hours of AI news and builds the page with the scripts in [scripts/](scripts/). It hands the Telegram message and the page to GitHub Actions, which send the message with repository secrets and publish the page only after it passes integrity and security checks.

## Documentation

All docs live in [docs/](docs/):

| | |
|---|---|
| [Architecture](docs/architecture.md) | Components, where each part runs, repo layout, state files, design rules |
| [Pipeline flow](docs/pipeline-flow.md) | One day's run, step by step |
| [Operations](docs/operations.md) | Health check, re-pinning the agent, changing scripts, rotating the token, troubleshooting |
| [Security](docs/SECURITY.md) | Threat model, controls, owner checklist |
| [Agent prompt](docs/agent-prompt.md) | The instructions the scheduled agent follows |
| [Run notes](docs/run-notes.md) | Incidents, workarounds, version history |

## Checks

```bash
python3 scripts/repo_audit.py && python3 -m unittest discover -s tests -v
```

These also run in GitHub Actions on every push and pull request. No credentials are ever committed. See [docs/SECURITY.md](docs/SECURITY.md).
