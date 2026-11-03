# AI News Daily — Documentation

Everything about how the daily briefing is built, delivered, operated and secured lives in this folder.

## Which document do I need?

| Document | Read it when you want to… |
|---|---|
| [architecture.md](architecture.md) | understand the system: components, where each part runs, repo layout, state files, the template lock and the design rules |
| [pipeline-flow.md](pipeline-flow.md) | follow one day's run step by step, from the 6:00 AM schedule to the Telegram message and the live page |
| [operations.md](operations.md) | do something: daily health check, re-pin the agent prompt, change a script or the template, rotate the token, troubleshoot a failure |
| [SECURITY.md](SECURITY.md) | see the threat model, the controls in place and the owner checklist |
| [agent-prompt.md](agent-prompt.md) | read or update the exact instructions the scheduled agent follows (this is the text pasted into Sarvam) |
| [run-notes.md](run-notes.md) | check past incidents, workarounds and the version history before changing anything risky |

## Key facts

| | |
|---|---|
| Live site | https://dilip457.github.io/ai-news-daily/ |
| Schedule (IST) | 6:00 AM main run · 9:30 AM and 5:30 PM watchdogs |
| Agent | "AI News Curator & Publisher" on Sarvam Cowork, connected to GitHub through Composio |
| Telegram | @Get_Excite_AI_News_bot → group "Daily AI news", sent from GitHub Actions |
| Secrets | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in repo **Settings → Secrets and variables → Actions**. Never in the repo. |
| Source of truth | this repo. The agent's sandbox is rebuilt from it on every run. |

## Repo map

```
.
├── README.md                     project summary (start here)
├── docs/                         all documentation (this folder)
├── scripts/                      pipeline + CI scripts, checksums.json
├── tests/                        security and delivery regression tests
├── .github/workflows/            deploy.yml, telegram-deliver.yml, checks.yml
├── master_template.html.gz.b64   the locked page design (gzip)
├── telegram_delivery_log.json    one-message-per-day record
├── index.html                    today's briefing (served by GitHub Pages)
└── updates/                      archive: one page per day
```

`index.html`, `updates/`, `.nojekyll`, the template and the delivery log stay at the repo root because GitHub Pages, the scripts and the workflows read them from there.
