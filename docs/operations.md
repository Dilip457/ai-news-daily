# Operations

Procedures for running and changing the pipeline. For how it works, see [architecture.md](architecture.md) and [pipeline-flow.md](pipeline-flow.md).

## Daily health check (1 minute, after 6:15 AM IST)

- [ ] One message arrived in the Telegram group "Daily AI news".
- [ ] https://dilip457.github.io/ai-news-daily/ shows today's date.
- [ ] Repo **Actions** tab: today's **Telegram Delivery** and **Deploy Briefing** runs are green.

If something is missing, go to [Troubleshooting](#troubleshooting). The 9:30 AM watchdog will also retry on its own.

## Re-pin the agent prompt

**When:** after merging any change to `scripts/` or `master_template.html.gz.b64`, after any change to [agent-prompt.md](agent-prompt.md), and after any history rewrite. The agent follows the text saved in Sarvam, not the file in this repo.

1. Note the commit to pin: the latest commit on `main` that changed `scripts/` or the template. The latest commit on `main` is also fine.
2. Generate the text to paste, from the repo root:
   ```bash
   SHA=$(git rev-parse origin/main)
   sed "s/<COMMIT_SHA>/$SHA/g" docs/agent-prompt.md > /tmp/agent-prompt-ready.md
   ```
   `BOOTSTRAP_SHA256` in the prompt must equal the `bootstrap.py` value in `scripts/checksums.json`. Update it in `agent-prompt.md` first if `bootstrap.py` changed.
3. In Sarvam Cowork: **Agents → AI News Curator & Publisher → Builder**. Replace all of the instructions with the generated text, then **Save**. The watchdogs use the same agent.
4. Test: in **Scheduled Tasks**, create a one-time task 5 minutes ahead, pointed at the same agent, with this text: *"Test only. Run STEP 0 and report whether the checksum printed OK and bootstrap was READY. Send nothing."* Expect `OK` and `BOOTSTRAP READY`, then delete the task.

## Change a pipeline script

1. Edit the script on a branch.
2. If it is listed in `scripts/checksums.json`, update its hash:
   ```bash
   python3 -c "import hashlib,json; p='scripts/checksums.json'; m=json.load(open(p)); n='telegram_deliver.py'; m[n]=hashlib.sha256(open('scripts/'+n,'rb').read()).hexdigest(); open(p,'w',newline='\n').write(json.dumps(m,indent=2)+'\n')"
   ```
   Replace `telegram_deliver.py` with the file you changed.
3. Run the checks: `python3 scripts/repo_audit.py && python3 -m unittest discover -s tests -v`
4. Open a PR. Wait for the **Checks** workflow to pass, then merge.
5. [Re-pin the agent prompt](#re-pin-the-agent-prompt). Until you do, the agent keeps running the old pinned version, which is safe.

CI-only scripts (`telegram_send.py`, `deploy_gate.py`, `repo_audit.py`) are not in the checksum list and don't need re-pinning. They take effect as soon as they're merged.

## Change the page template

The validator compares every page to the template byte for byte, so template changes need care:

1. Decompress: `python3 -c "import gzip; open('t.html','wb').write(gzip.decompress(open('master_template.html.gz.b64','rb').read()))"`
2. Edit `t.html`. If you change an inline `<script>`, recompute its `'sha256-…'` hash in the Content-Security-Policy meta tag:
   ```bash
   python3 -c "import re,hashlib,base64; h=open('t.html',encoding='utf-8').read(); [print(\"'sha256-\"+base64.b64encode(hashlib.sha256(b.encode()).digest()).decode()+\"'\") for b in re.findall(r'<script[^>]*>(.*?)</script>',h,re.S) if b.strip()]"
   ```
3. Recompress deterministically: `python3 -c "import gzip; open('master_template.html.gz.b64','wb').write(gzip.compress(open('t.html','rb').read(),9,mtime=0))"`
4. Update `master_template.html` in `scripts/checksums.json`. The hash is of the **decompressed** HTML.
5. Open the page in a browser and check the console for CSP errors. Then run the checks, open a PR, merge and [re-pin](#re-pin-the-agent-prompt).

Archived pages in `updates/` keep the template they were built with.

## Rotate the Telegram token

1. Telegram → **@BotFather** → `/mybots` → **@Get_Excite_AI_News_bot** → **API Token** → **Revoke current token**. Copy the new token. The bot, the group and the chat ID stay the same.
2. Repo **Settings → Secrets and variables → Actions** → `TELEGRAM_BOT_TOKEN` → **Update** → paste.
3. If the Sarvam secret store still holds `TELEGRAM_BOT_TOKEN` (legacy PATH B), update it as well, or better, delete it.
4. Check the new token: open `https://api.telegram.org/bot<NEW_TOKEN>/getMe` in your browser. Expect `"ok":true`. This sends nothing.

Never paste the token into the agent chat, the prompt, an issue or a commit.

## Run the checks locally

```bash
python3 scripts/repo_audit.py                   # checksums + secret scan
python3 -m unittest discover -s tests -v        # 31 security and delivery tests
```

Both run automatically in **Checks** on every push and PR.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No Telegram message, and the log has `last_error` for today | The send failed (wrong or revoked token, bot removed from the group) | Read the **Telegram Delivery** run log. A `401` means [rotate the token](#rotate-the-telegram-token). `chat not found` means re-add the bot to the group. |
| No Telegram message, and no Telegram Delivery run today | The agent run failed before step 4, or never started | Check the agent's session history in Sarvam. The 9:30 watchdog retries automatically. |
| Alert "FAILED at step 0" / `checksum mismatch` | The prompt pins a commit that doesn't exist or doesn't match | [Re-pin the agent prompt](#re-pin-the-agent-prompt) |
| Workflow output `CONFIG ERROR` | A repo secret is missing or malformed | Re-add `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` under Actions secrets |
| Message sent, site still shows yesterday | Deploy gate rejected the page, or deploy didn't fire | **Deploy Briefing** run: `REJECTED — <reason>` explains the rejection. If there was no run and `data.manifest.json` is still on `main`, go to **Actions → Deploy Briefing → Run workflow** once. |
| `data.gz.b64.part*` files left on `main` | A deploy was rejected or interrupted | Harmless. They're overwritten by the next publish and deleted by the next successful deploy. |
| Two messages on the same day | A delivery-log commit was lost (fixed by push-retry since v4.2) | Check that `telegram_delivery_log.json` has exactly one `sent` entry for the date |
| **Checks** red: checksum mismatch | A script changed without updating `checksums.json` | Follow [Change a pipeline script](#change-a-pipeline-script), step 2 |
| **Checks** red: credential found | A token or key was committed | Revoke the credential **first**, then remove it from the files. See [SECURITY.md](SECURITY.md). |

## Never do

- Use `GITHUB_CREATE_A_TREE` for publishing. On 2026-10-31 it emptied the repo ([run-notes.md](run-notes.md)).
- Edit scripts inside the agent sandbox after bootstrap. That defeats the checksum check.
- Put a token or password in any file, prompt or commit message.
- Grant the agent's GitHub connection permission to edit workflows or read secrets.
