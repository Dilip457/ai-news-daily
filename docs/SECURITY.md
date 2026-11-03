# Security

## Threat model

The pipeline reads untrusted content from the open web every day, and has write access to this repo and to a Telegram group. The realistic attackers are:

| Attacker | Goal | Controls |
|---|---|---|
| Anyone reading this public repo | Abuse leaked credentials | No secrets in the repo or its history. The bot token lives only in GitHub Actions secrets. `repo_audit.py` scans every push for tokens and keys. |
| A malicious news page or headline | XSS on `dilip457.github.io` (shared by all of the owner's Pages sites), or phishing links in Telegram | Generator validation, the modal rendered with `textContent`, http(s)-only links, a CSP, plain-text Telegram messages |
| Prompt injection inside fetched pages | Make the agent change scripts or workflows, push other files, or exfiltrate the token | The "untrusted content" rules in [agent-prompt.md](agent-prompt.md); the token never enters the agent's sandbox; pinned scripts; the CI deploy gate; a scoped GitHub connection (owner item 3) |
| Compromised CDN (cdnjs) | Serve modified Three.js to every visitor | Subresource Integrity (sha384) on the script tag, plus the CSP allowlist |
| Bad or tampered push to `main` | Change what the scheduled agent executes | Bootstrap pinned to a commit SHA (`AI_NEWS_REF`) and checked against a hash held in the agent prompt. Every file must match `checksums.json`. |
| Corruption in transit | A broken or partial page goes live | SHA-256 manifest for each part and for the whole page, strict base64, capped gunzip, the validator re-run in Actions |

## Controls in this repo

- **Page:** a CSP meta tag (`default-src 'none'`, hashed inline scripts, Three.js by exact URL, no inline handlers), SRI on Three.js, `referrer: no-referrer`, and the modal built with DOM APIs.
- **Generator** (`generate_briefing_fixed.py`): type and length limits, http(s)-only URLs, stripped control and bidi characters, clamped importance, stats recomputed from the articles, all output HTML-escaped.
- **Validator** (`template_validator.py`, run in the agent and in CI): byte-identical CSS/JS, identical CSP and Three.js tag, no `on*=` attributes, no non-http(s) URLs, no extra script/iframe/object/embed/form/base/meta/link tags, no new external origins.
- **Deploy** (`deploy.yml` + `deploy_gate.py`): runs only when `data.manifest.json` is pushed, with least-privilege permissions, a pinned `actions/checkout`, serialized runs, push retry, and fails closed.
- **Telegram delivery** (`telegram-deliver.yml` + `telegram_send.py`): the token stays on the Actions runner as a repository secret, so it never enters the agent's sandbox and no URL carrying it is ever built there. Messages are plain text with previews off, and at most one briefing and one alert go out per IST date, enforced in code.
- **Legacy delivery** (`telegram_deliver.py`, PATH B only): credentials from the platform environment, the URL never printed, files written with mode 0600.
- **Checks** (`checks.yml`): checksum and secret audit plus the test suite on every push and PR.
- **Line endings** (`.gitattributes`): forced to LF, because the CSP hashes and checksums depend on exact bytes.

## Owner checklist (cannot be done from the repo)

| # | Action | Status |
|---|---|---|
| 1 | Revoke the leaked bot token in @BotFather | **Done**: the old token returns `401` (checked 2026-11-03) |
| 2 | Store `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` in repo **Settings → Secrets and variables → Actions** | **Done** (2026-11-03) |
| 3 | Reconnect the agent's GitHub access with a **fine-grained token**: this repo only, *Contents* + *Actions* read & write, **no** *Workflows*, **no** *Secrets*. Anyone who can push a workflow file can make Actions reveal the repo secret, so workflow-write access is effectively access to the token. | **Open**: the current Composio OAuth connection can write workflows |
| 4 | Re-pin `AI_NEWS_REF` / `BOOTSTRAP_SHA256` in the Sarvam prompt after script changes ([how](operations.md#re-pin-the-agent-prompt)) | Ongoing |
| 5 | Repo **Settings → Code security**: enable *Secret scanning* and *Push protection* | Open |
| 6 | Delete `TELEGRAM_BOT_TOKEN` from the Sarvam secret store once PATH A has delivered for a few days | Open |
| 7 | Purge the old token from git history | **Done**: history rewritten 2026-11-03, 0 occurrences in a fresh clone. Leftover: GitHub still serves old commits through the merged PR #1 ref and its cache. Ask https://support.github.com ("Remove sensitive data") to purge them. |
| 8 | Optional, if your plan offers push rulesets with file-path restrictions: block direct pushes touching `scripts/**`, `.github/**` and `master_template.html.gz.b64` | Optional |

## If a secret is ever exposed

1. **Revoke it first.** Deleting it from files or history does not make it safe.
2. Put the replacement only in a secret store ([rotate the Telegram token](operations.md#rotate-the-telegram-token)).
3. Remove it from the files. If it was pushed, consider a history rewrite and a GitHub Support purge.
4. Record the incident in [run-notes.md](run-notes.md).

## Reporting

Please open a private security advisory on this repository rather than a public issue.
