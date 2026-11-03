# Run notes

Append-only log of pipeline incidents, the workarounds adopted, and the version history.
Read it before touching the publish step. Newest entries are at the bottom.

## Version history

| Version | Date | Summary |
|---|---|---|
| v3 | Sept 2026 | Single 6 AM run, single `data.gz.b64` push, local dedup log |
| v4.1 | Sept 2026 | Watchdog runs (9:30 AM, 5:30 PM), `bootstrap.py` with checksums, 4-part chunked publish, delivery log in the repo |
| v4.2 | 2026-11-02 | Security hardening: no secrets in the repo, XSS fix + CSP + SRI, input validation, pinned bootstrap, manifest-gated deploy, CI audit + tests |
| v4.3 | 2026-11-03 | Telegram sent from GitHub Actions (repo secrets), alert messages, push retries, history purged of the old token, docs consolidated in `docs/` |

### v4.1 → v4.2 in detail

| Area | v4.1 | v4.2 |
|------|------|------|
| Credentials | Bot token + chat ID hardcoded in two public scripts | Secrets outside the repo; CI secret scan on every push (v4.3: repo secrets on the Actions runner) |
| Page XSS | Modal rendered article fields with `innerHTML`; any scraped headline could run script | DOM/`textContent` rendering, http(s)-only links, CSP with hashed scripts, no inline handlers |
| Third-party JS | Three.js from cdnjs with no integrity check | SRI sha384 + CSP allowlist |
| Input handling | Agent JSON trusted as-is (`javascript:` URLs, non-numeric scores, regex-escape bugs) | Schema/length/URL validation, stats recomputed, regex replacements via callables |
| Script supply chain | Fetched from `main`; checksum skipped when missing from the manifest | Pinned commit + bootstrap hash in the prompt; unlisted files fail |
| Deploy | Triggered by each part push; assembled blindly; first-date-in-file used as name | Triggered by the manifest; SHA-256 verified; validator re-run in CI; pinned action; least privilege |
| Delivery log | Scripts expected a flat object; repo used `{"sent": [...]}`, so the helpers were broken | One format everywhere, IST dates, duplicate refusal in code, always refreshed from `main` |
| Briefing box | Only the first paragraph was replaced, so the Aug 29 sample paragraphs appeared on every page | Whole box replaced; archived pages cleaned |
| Paths | `/workspace/notes` hardcoded and rewritten by hand each run (breaking checksums) | `AI_NEWS_HOME` / `AI_NEWS_WORK` with `/scratch/work` defaults |
| Docs | The prompt still prescribed `GITHUB_CREATE_A_TREE` | Prompt, notes and architecture agree |

## 2026-10-31 — GITHUB_CREATE_A_TREE collapsed the repository tree

**What happened.** The chunked publish built 4 verified blobs (all SHA-matched) and then
called `GITHUB_CREATE_A_TREE` with `base_tree` set to the current main tree plus 4 blob
entries. The returned tree contained only `workflows/deploy.yml` — every other file
(scripts, template, index.html, updates/, delivery log) was dropped from the tree, and
the ref update to that commit briefly emptied main.

**Recovery.** Re-created a commit whose `tree` was the known-good tree SHA from the
preceding commit (67 paths) with the broken commit as parent, then fast-forwarded main.
No history rewrite and no force push was needed. The full tree was verified before
proceeding.

**Workaround now in use.** Do not use `GITHUB_CREATE_A_TREE` for the publish step.
Instead:

1. `GITHUB_CREATE_A_BLOB` for each of `data.gz.b64.part1..4`, verifying each returned
   SHA against the locally computed `sha1("blob <len>\0" + content)`.
2. `GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS` to write each part to its path. This path is
   proven safe — it preserves the rest of the tree.
3. `GITHUB_CREATE_A_WORKFLOW_DISPATCH_EVENT` on `deploy.yml` only if the push-triggered
   run did not fire. Note that pushing the parts already triggers `deploy.yml` (its
   trigger is `push` on `data.gz.b64.part*`), so an extra dispatch usually produces a
   redundant run that fails harmlessly because the parts are already cleaned up.
   *(Superseded in v4.2: `deploy.yml` now triggers on `data.manifest.json`, which is
   pushed last.)*
4. Verify by reading the tree of `main` — expect 68 paths, no `data.gz.b64.part*`
   remaining, `index.html` present, and `updates/<DATE>.html` present.

**Always verify the tree after any tree/commit write.** A tree write that silently drops
entries is indistinguishable from success at the API level.

## Environment note

`/workspace` is not writable in this sandbox. Since v4.2 every script reads
`AI_NEWS_HOME` (default `/scratch/work/notes`) and `AI_NEWS_WORK` (default
`/scratch/work`), so **do not rewrite paths inside the scripts** any more. Editing a
script after bootstrap silently defeats the checksum verification.

## 2026-11-02 — Security review and hardening (v4.2)

**Found.**
1. The Telegram bot token and chat ID were hardcoded in `scripts/telegram_deliver.py`
   and `scripts/pipeline_validator.py`, in a public repo. `pipeline_validator.py`
   also printed the full send URL, token included, into the run output.
2. Stored XSS: the page's modal rendered article fields with `innerHTML`, and the
   generator only escaped quotes in `data-article`. A scraped headline such as
   `<img src=x onerror=...>` executed on click (reproduced in Chrome). `javascript:`
   URLs were also accepted.
3. Three.js was loaded from cdnjs with no SRI, and the page had no CSP.
4. Bootstrap skipped verification for files missing from `checksums.json`, always
   fetched from `main`, and kept a stale local delivery log (double-send risk).
5. The delivery-log format in the scripts (`{status, message_id}`) did not match the
   repo (`{"sent": [...]}`): `telegram_deliver.py --validate` would crash, and
   `pipeline_validator.py` always reported "pending".
6. Only the first `<p>` of the template's briefing box was replaced, so every page
   since launch showed the Aug 29 sample paragraphs as that day's news.
7. `CRON_PROMPT.md` still prescribed `GITHUB_CREATE_A_TREE` (see the incident above).

**Changed.** Env-var credentials, plain-text Telegram messages, the token never printed;
generator input validation; a DOM-based modal, CSP and SRI in the template (also applied
to `index.html` and all `updates/` pages, and stale paragraphs removed); pinned and
mandatory checksums in bootstrap; a manifest-triggered, SHA-256-verified and
validator-gated deploy in Actions; `checks.yml` (checksums + secret scan + tests);
CRON_PROMPT v4.2. Details in `architecture.md` and `SECURITY.md` (then at the repo root, now in `docs/`).

**Owner actions still required.** Revoke the old bot token in @BotFather, set the new
one as a platform secret, scope the agent's GitHub token, and pin `AI_NEWS_REF` /
`BOOTSTRAP_SHA256` in the prompt (see the SECURITY.md checklist). Until the prompt is
updated, the old v4.1 instructions will fail at bootstrap because they hardcode
`/workspace` paths and the old checksums. Update the prompt in the same session as
the merge.

## 2026-11-03 — Telegram delivery moved to GitHub Actions (PATH A)

**What changed.** The agent now writes `telegram/outbox.json`. `telegram-deliver.yml`
sends it from the Actions runner with `scripts/telegram_send.py`, using the
`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` repository secrets, then commits the delivery
log and removes the outbox (`[skip ci]`). The token no longer enters the agent sandbox
or any fetch-tool URL. The old `web_get_contents` route stays as PATH B. End-to-end
test: workflow run 41619987055, message_id 93.

**Log note.** The test cleared and re-recorded today's entry, so the log shows
message_id 93 for 2026-11-03. The real morning briefing was message_id 90 (see commit
68bd18d; it was 87bdc5e before the history rewrite below).

**Follow-ups applied the same day.**
- Both `telegram-deliver.yml` and `deploy.yml` now rebase and retry a rejected push. A
  lost log commit would leave the outbox in place and allow a duplicate send.
- Outbox `"kind": "alert"`: one failure alert per date can still go out after the
  briefing was delivered, so failures are never silent on PATH A.
- The agent no longer lists repository secrets to choose a path (it uses PATH A and
  falls back on `CONFIG ERROR`), so its token needs no secrets permission.
- Removed the one-off `telegram-resolve-chat.yml` debug workflow.

**Open.** The agent's GitHub connection can write workflow files, which now means it
could reach the repository secrets. See SECURITY.md item 3.

## 2026-11-03 — Git history rewritten to purge the leaked token

**What.** The old Telegram bot token (already revoked; it returns `401`) was still
readable in past versions of `scripts/telegram_deliver.py`, `scripts/pipeline_validator.py`
and `ai-news-architecture.md`. The history was rewritten with `git filter-repo
--replace-text`, which replaced the token with `***REMOVED-TELEGRAM-TOKEN***`, and
force-pushed. A fresh clone contains 0 occurrences, and the current files were unchanged.

**Consequences.**
- **Every commit ID changed.** Any SHA recorded before 2026-11-03 13:40 IST (including
  the agent prompt's old `AI_NEWS_REF` d0d361e) no longer exists. The prompt was re-pinned.
- Local clones from before the rewrite must be re-cloned. Do not push from them.
- GitHub still serves the old commits through the merged PR #1 ref and its cache until
  GitHub Support purges them (SECURITY.md owner item 7).

## 2026-11-03 — Documentation consolidated in `docs/`

The five scattered root files became one folder. Moved with history:
`ai-news-architecture.md` → `docs/architecture.md`, `CRON_PROMPT.md` →
`docs/agent-prompt.md`, `RUN_NOTES.md` → `docs/run-notes.md`, `SECURITY.md` →
`docs/SECURITY.md` (GitHub still detects it there). New: `docs/README.md` (index),
`docs/pipeline-flow.md` (daily working flow) and `docs/operations.md` (runbook).

While reorganizing, these stale statements were corrected:
- The agent prompt's write-allowlist omitted `telegram/outbox.json` (the PATH A file),
  and its secrets and alert sections described only the legacy path → v4.3.
- The architecture doc still described Telegram via `web_get_contents`.
- SECURITY.md said credentials came from env vars, and listed revocation and the
  history purge as still to do.

No script, workflow or checksum changed. The agent prompt *text* changed, so it was re-pasted
into Sarvam.
