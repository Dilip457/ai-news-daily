# Security

## Threat model

The pipeline reads untrusted content from the open web every day and has write access to this repo and a Telegram group. The realistic attackers are:

| Attacker | Goal | Controls |
|---|---|---|
| Anyone reading this public repo | Abuse leaked credentials | No secrets in the repo: the bot token and chat ID come from env vars. `repo_audit.py` scans every push for tokens and keys. |
| A malicious news page or headline | XSS on `dilip457.github.io` (shared by all of the owner's Pages sites), phishing links in Telegram | Generator validation, the modal renders with `textContent`, http(s)-only links, CSP, plain-text Telegram messages |
| Prompt injection inside fetched pages | Make the agent change scripts, push other files or leak the token | "Untrusted content" rules in `CRON_PROMPT.md`, a scoped GitHub token, pinned scripts, the CI deploy gate |
| Compromised CDN (cdnjs) | Serve modified Three.js to every visitor | Subresource Integrity (sha384) on the script tag, plus a CSP allowlist |
| Bad or tampered push to `main` | Change what the scheduled agent executes | Bootstrap pinned to a commit SHA (`AI_NEWS_REF`) and checked against a hash held in the agent prompt. Every file must match `checksums.json`. |
| Corruption in transit | Broken or partial page goes live | SHA-256 manifest for each part and for the whole page, strict base64, capped gunzip, validator re-run in Actions |

## Controls in this repo

- **Page:** a CSP meta tag (`default-src 'none'`, hashed inline scripts, Three.js by exact URL, no inline handlers), SRI on Three.js, `referrer: no-referrer`, and the modal built with DOM APIs.
- **Generator** (`generate_briefing_fixed.py`): type and length limits, http(s)-only URLs, stripped control and bidi characters, clamped importance, stats recomputed from the articles, all output HTML-escaped.
- **Validator** (`template_validator.py`, run locally AND in CI): byte-identical CSS/JS, identical CSP and Three.js tag, no `on*=` attributes, no non-http(s) URLs, no extra script/iframe/object/embed/form/base/meta/link tags, no new external origins.
- **Deploy** (`deploy.yml` + `deploy_gate.py`): runs only when `data.manifest.json` is pushed, has least-privilege permissions, a pinned `actions/checkout`, serialized runs, and fails closed.
- **Checks** (`checks.yml`): checksum and secret audit plus the security test suite on every push and PR.
- **Telegram** (`telegram_deliver.py`): credentials from env, the URL never printed (files are written 0600), plain text only, at most one message per IST day, enforced in code.

## Owner checklist (cannot be done from the repo)

1. **Revoke the leaked bot token now.** It was committed in `scripts/telegram_deliver.py` and `scripts/pipeline_validator.py` and is still in git history. In Telegram, open @BotFather → `/mybots` → the bot → API Token → **Revoke current token**. Removing it from the files does not make the old token safe.
2. Put the new token and the chat ID into the agent platform's secret store as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Never paste them into the prompt text or the repo.
3. Give the agent a **fine-grained GitHub token** scoped to this one repo with *Contents: read & write* and *Actions: read & write* (for the dispatch fallback) and **no** *Workflows* permission, so it cannot edit `.github/workflows/`.
4. After merging, set `AI_NEWS_REF` in the agent prompt to the merge commit SHA, and set `BOOTSTRAP_SHA256` to the `bootstrap.py` value in `scripts/checksums.json`. Repeat whenever scripts change.
5. In repo **Settings → Code security**, enable *Secret scanning* and *Push protection*.
6. Optional, if your plan offers push rulesets with file-path restrictions: block direct pushes touching `scripts/**`, `.github/**` and `master_template.html.gz.b64`, so those changes only arrive through reviewed PRs.
7. Optional, after step 1: purge the old token from history with `git filter-repo` and force-push. This is not needed for safety once the token is revoked.

## Reporting

Please open a private security advisory on this repository rather than a public issue.
